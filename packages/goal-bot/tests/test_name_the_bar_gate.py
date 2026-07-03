"""B5 — the name-the-bar structural gate + Tier-3 hypotheses (OQ-COMP-1, D-11).

The load-bearing assertion: a miss count is NOT reachable from the assembled
morning context — it lives only behind `get_miss_detail`, called after assent.
"""

import json
from datetime import date, timedelta

import pytest
from goal_bot.application.morning_context import (
    InsightHypothesis,
    MorningContext,
    ReassessmentNudge,
)
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    DailyPlanItem,
    Goal,
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
)
from goal_bot.infrastructure import tables as t
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from sqlalchemy import insert

TODAY = date(2026, 6, 27)

_BANNED_COUNT_KEYS = ("count", "miss", "streak", "tally", "fail")
_BANNED_PARTNER = ("partner", "compare", "versus", "jade", "relative_to")


def _make_goal(goal_repo, person_id, title, *, level=Level.NEED):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title=title))
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=level,
            definition=title,
            version_no=1,
            recurrence_type=RecurrenceType.DAILY,
            recurrence_config={},
            completion_type=CompletionType.BINARY,
        )
    )
    return g, v


def _assemble(engine, person_id, **kw):
    return assemble_morning_context(
        person_id,
        TODAY,
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
        **kw,
    )


def _uc(engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )


# --- the structural gate (most important) ----------------------------------


def test_nudge_payload_model_has_no_count_field():
    # The reassessment payload carries offers only — no count/miss/streak field.
    fields = set(ReassessmentNudge.model_fields)
    assert fields == {"goal_id", "goal_title", "goal_type", "offers"}
    for f in fields:
        assert not any(b in f for b in _BANNED_COUNT_KEYS)


def test_morning_context_has_no_miss_count_field():
    for f in MorningContext.model_fields:
        assert not any(b in f for b in _BANNED_COUNT_KEYS)


@pytest.mark.integration
def test_assembled_context_exposes_no_miss_count(migrated_engine, goal_repo, person_id):
    g, _ = _make_goal(goal_repo, person_id, "Meditate")
    # drive the goal over the engaged-miss threshold (7)
    for _ in range(7):
        goal_repo.advance_carry_over(g.id)

    ctx = _assemble(migrated_engine, person_id)
    assert ctx.reassessment is not None  # nudge fires...

    blob = json.dumps(ctx.model_dump(), default=str).lower()
    # ...but the count (7) and its day-by-day never appear in the context
    assert "engaged_miss_count" not in blob
    assert "carried over 7" not in blob
    # the reassessment payload itself has no count-bearing key
    assert set(ctx.reassessment.model_dump()) == {
        "goal_id",
        "goal_title",
        "goal_type",
        "offers",
    }


@pytest.mark.integration
def test_get_miss_detail_is_the_only_source_of_the_count(
    migrated_engine, goal_repo, person_id
):
    g, _ = _make_goal(goal_repo, person_id, "Meditate")
    for _ in range(7):
        goal_repo.advance_carry_over(g.id)
    # the count is reachable ONLY through the assent-gated read
    detail = _uc(migrated_engine).get_miss_detail(g.id)
    assert "engaged_miss_count" in detail


@pytest.mark.integration
def test_assemble_never_calls_the_miss_detail_read(
    migrated_engine, goal_repo, person_id, monkeypatch
):
    _make_goal(goal_repo, person_id, "Meditate")

    def _boom(*a, **k):
        raise AssertionError("list_engaged_miss_dates called during assemble")

    monkeypatch.setattr(SqlAlchemyPlanRepository, "list_engaged_miss_dates", _boom)
    # assemble must complete without ever touching the miss-detail read
    _assemble(migrated_engine, person_id)


# --- engaged-only counting (silence is never a miss) -----------------------


@pytest.mark.integration
def test_miss_detail_counts_engaged_misses_only(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _make_goal(goal_repo, person_id, "Meditate")
    # 3 days: not_done, planned (silence), not_done  → only the 2 not_done count
    for i, status in enumerate(
        [PlanItemStatus.NOT_DONE, PlanItemStatus.PLANNED, PlanItemStatus.NOT_DONE]
    ):
        d = TODAY - timedelta(days=i + 1)
        plan = plan_repo.get_or_create_plan(person_id, d)
        item = plan_repo.add_plan_item(
            DailyPlanItem(daily_plan_id=plan.id, goal_id=g.id, goal_version_id=v.id)
        )
        if status != PlanItemStatus.PLANNED:
            plan_repo.set_item_outcome(item.id, status)

    detail = _uc(migrated_engine).get_miss_detail(g.id)
    assert detail["engaged_miss_count"] == 2  # silence excluded
    assert len(detail["engaged_miss_dates"]) == 2


# --- Tier-3 hypotheses (D-11) ----------------------------------------------


@pytest.mark.integration
def test_active_insight_surfaces_as_hypothesis_object(
    migrated_engine, goal_repo, person_id
):
    with migrated_engine.begin() as c:
        c.execute(
            insert(t.insight).values(
                person_id=person_id,
                content="slips after short-sleep nights",
                status="active",
                derived_from={"pattern": "sleep"},
            )
        )
    insights = goal_repo.list_active_insights(person_id)
    assert len(insights) == 1
    # it maps to a confirm/reject hypothesis object, not a verdict string
    h = InsightHypothesis(
        insight_id=insights[0].id,
        text=insights[0].content,
        basis=insights[0].derived_from,
    )
    assert h.text == "slips after short-sleep nights"
    assert h.basis == {"pattern": "sleep"}


@pytest.mark.integration
def test_dismissed_insight_not_surfaced(migrated_engine, goal_repo, person_id):
    with migrated_engine.begin() as c:
        c.execute(
            insert(t.insight).values(
                person_id=person_id,
                content="old pattern",
                status="dismissed",
            )
        )
    assert goal_repo.list_active_insights(person_id) == []


# --- win-always-present + comparison guard ---------------------------------


@pytest.mark.integration
def test_win_surface_nonempty_or_thin_day(migrated_engine, goal_repo, person_id):
    # nothing to surface → thin_day flag is set (never silently empty)
    ctx = _assemble(migrated_engine, person_id)
    assert bool(ctx.win_surface) or ctx.thin_day is True


def test_no_surfaced_model_references_the_partner():
    # comparison guard (D-10/D-15): no surfaced payload has a partner field
    for model in (ReassessmentNudge, InsightHypothesis, MorningContext):
        for f in model.model_fields:
            assert not any(b in f.lower() for b in _BANNED_PARTNER)

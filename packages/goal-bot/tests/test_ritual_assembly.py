from datetime import date, timedelta

import pytest
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.domain.entities import (
    Chapter,
    CompletionType,
    DailyPlanItem,
    Goal,
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository

TODAY = date(2026, 6, 27)
YESTERDAY = TODAY - timedelta(days=1)

_VKW = dict(
    version_no=1,
    recurrence_type=RecurrenceType.DAILY,
    recurrence_config={},
    completion_type=CompletionType.BINARY,
)


def _make_goal(
    goal_repo,
    person_id,
    title,
    *,
    level=Level.NEED,
    why=None,
    chapter_id=None,
    recurrence=RecurrenceType.DAILY,
    recurrence_config=None,
):
    g = goal_repo.create_goal(
        Goal(owner_profile_id=person_id, title=title, chapter_id=chapter_id)
    )
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=level,
            definition=title,
            why=why,
            version_no=1,
            recurrence_type=recurrence,
            recurrence_config=recurrence_config or {},
            completion_type=CompletionType.BINARY,
        )
    )
    return g, v


def _assemble(migrated_engine, person_id):
    return assemble_morning_context(
        person_id,
        TODAY,
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


@pytest.mark.integration
def test_mixed_yesterday(migrated_engine, goal_repo, plan_repo, person_id):
    g_done, v_done = _make_goal(goal_repo, person_id, "Move", why="energy")
    g_nd, v_nd = _make_goal(goal_repo, person_id, "Read")
    g_silent, v_silent = _make_goal(goal_repo, person_id, "Write")

    yplan = plan_repo.get_or_create_plan(person_id, YESTERDAY)
    i_done = plan_repo.add_plan_item(
        DailyPlanItem(
            daily_plan_id=yplan.id, goal_id=g_done.id, goal_version_id=v_done.id
        )
    )
    plan_repo.set_item_outcome(i_done.id, PlanItemStatus.DONE)
    i_nd = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=yplan.id, goal_id=g_nd.id, goal_version_id=v_nd.id)
    )
    plan_repo.set_item_outcome(i_nd.id, PlanItemStatus.NOT_DONE)
    plan_repo.add_plan_item(
        DailyPlanItem(
            daily_plan_id=yplan.id, goal_id=g_silent.id, goal_version_id=v_silent.id
        )
    )  # stays planned

    ctx = _assemble(migrated_engine, person_id)

    statuses = {yi.goal_title: yi.status for yi in ctx.yesterday}
    assert statuses["Move"] == "done"
    assert statuses["Read"] == "not_done"
    assert statuses["Write"] == "planned"

    # done item produces a derived win
    derived = [w for w in ctx.win_surface if w.source == "derived"]
    assert derived, f"expected a derived win, got {ctx.win_surface}"
    assert derived[0].text == "Move"
    assert derived[0].why == "energy"

    carry_ids = {c.goal_id for c in ctx.full_list if c.is_carry_over}
    assert g_nd.id in carry_ids
    assert g_silent.id in carry_ids
    assert g_done.id not in carry_ids


@pytest.mark.integration
def test_null_tolerance_planned_is_carry_over_not_miss(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _make_goal(goal_repo, person_id, "Meditate")
    yplan = plan_repo.get_or_create_plan(person_id, YESTERDAY)
    plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=yplan.id, goal_id=g.id, goal_version_id=v.id)
    )  # stays planned (silence)

    ctx = _assemble(migrated_engine, person_id)

    # silence shows as planned, never as not_done
    assert ctx.yesterday[0].status == "planned"
    # the silent goal is a carry-over candidate
    carry_ids = {c.goal_id for c in ctx.full_list if c.is_carry_over}
    assert g.id in carry_ids
    # no item in yesterday has status not_done from silence
    for yi in ctx.yesterday:
        if yi.goal_title == "Meditate":
            assert yi.status != "not_done"


@pytest.mark.integration
def test_thin_day(migrated_engine, goal_repo, person_id):
    _make_goal(goal_repo, person_id, "Run")

    ctx = _assemble(migrated_engine, person_id)

    assert ctx.thin_day is True
    assert ctx.win_surface == []
    assert len(ctx.candidates) >= 1  # goal still surfaces


@pytest.mark.integration
def test_subset_vs_full_list(migrated_engine, goal_repo, plan_repo, person_id):
    chapter_id = goal_repo.create_chapter(
        __import__("goal_bot.domain.entities", fromlist=["Chapter"]).Chapter(
            owner_profile_id=person_id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    ).id

    # 6 want-level one-offs with near targets (due per spec §3 bucket 3) →
    # suggested/trimmable; a daily need → must-show.
    for i in range(6):
        _make_goal(
            goal_repo,
            person_id,
            f"Want {i}",
            level=Level.WANT,
            chapter_id=chapter_id,
            recurrence=RecurrenceType.ONEOFF,
            recurrence_config={"target": (TODAY + timedelta(days=2)).isoformat()},
        )
    g_need, _ = _make_goal(goal_repo, person_id, "Daily need", chapter_id=chapter_id)
    # one chapter-less goal
    g_naked, _ = _make_goal(goal_repo, person_id, "Chapterless goal")

    ctx = _assemble(migrated_engine, person_id)

    # Suggested (non-need) items are trimmed to the realism cap...
    suggested = [c for c in ctx.candidates if c.bucket == "suggested"]
    assert len(suggested) <= 3
    # ...but the need is a protected promise — always present, never trimmed.
    assert any(c.goal_id == g_need.id for c in ctx.candidates)
    # trimmed-out non-needs are offered back via the lighter-day nudge
    assert len(ctx.nudge_offer) >= 1

    assert len(ctx.full_list) >= 8
    full_ids = {c.goal_id for c in ctx.full_list}
    candidate_ids = {c.goal_id for c in ctx.candidates}
    assert candidate_ids.issubset(full_ids)
    assert g_naked.id in full_ids


@pytest.mark.integration
def test_version_pinning_prefers_need(migrated_engine, goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="Meditate"))
    v_need = goal_repo.create_goal_version(
        GoalVersion(goal_id=g.id, level=Level.NEED, definition="5 min", **_VKW)
    )
    goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            version_no=2,
            level=Level.WANT,
            definition="20 min",
            recurrence_type=RecurrenceType.DAILY,
            recurrence_config={},
            completion_type=CompletionType.BINARY,
        )
    )

    ctx = _assemble(migrated_engine, person_id)

    pinned = next(c for c in ctx.full_list if c.goal_id == g.id)
    assert pinned.goal_version_id == v_need.id
    assert pinned.level == "need"


@pytest.mark.integration
def test_chapter_preamble_flows_into_context(migrated_engine, goal_repo, person_id):
    goal_repo.create_chapter(
        Chapter(
            owner_profile_id=person_id,
            label="Reset",
            preamble="strength focus; guitar parked this season",
            start_date=TODAY - timedelta(days=5),
            end_date=TODAY + timedelta(days=25),
        )
    )
    ctx = _assemble(migrated_engine, person_id)
    assert ctx.chapter_label == "Reset"
    assert ctx.chapter_preamble == "strength focus; guitar parked this season"


@pytest.mark.integration
def test_no_active_chapter_means_no_preamble(migrated_engine, person_id):
    ctx = _assemble(migrated_engine, person_id)
    assert ctx.chapter_label is None
    assert ctx.chapter_preamble is None


@pytest.mark.integration
def test_oneoff_without_target_stays_out_of_candidates(
    migrated_engine, goal_repo, person_id
):
    """Spec §3 bucket 3 (OQ-10): a no-target one-off is full-list-only — the
    errand pile must not flood the morning."""
    g, _ = _make_goal(
        goal_repo, person_id, "Renew passport", recurrence=RecurrenceType.ONEOFF
    )
    ctx = _assemble(migrated_engine, person_id)
    assert g.id in {c.goal_id for c in ctx.full_list}
    assert g.id not in {c.goal_id for c in ctx.candidates}


@pytest.mark.integration
def test_oneoff_with_near_target_surfaces(migrated_engine, goal_repo, person_id):
    g_near, _ = _make_goal(
        goal_repo,
        person_id,
        "Register the Bronco",
        recurrence=RecurrenceType.ONEOFF,
        recurrence_config={"target": (TODAY + timedelta(days=3)).isoformat()},
    )
    g_far, _ = _make_goal(
        goal_repo,
        person_id,
        "Renew passport",
        recurrence=RecurrenceType.ONEOFF,
        recurrence_config={"target": (TODAY + timedelta(days=30)).isoformat()},
    )
    ctx = _assemble(migrated_engine, person_id)
    candidate_ids = {c.goal_id for c in ctx.candidates}
    assert g_near.id in candidate_ids
    assert g_far.id not in candidate_ids


@pytest.mark.integration
def test_carried_oneoff_without_target_still_surfaces(
    migrated_engine, goal_repo, plan_repo, person_id
):
    """Carry-over presence tracking beats the target rule — a sliding promise
    is never silently dropped."""
    g, v = _make_goal(
        goal_repo, person_id, "Cancel membership", recurrence=RecurrenceType.ONEOFF
    )
    yplan = plan_repo.get_or_create_plan(person_id, YESTERDAY)
    plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=yplan.id, goal_id=g.id, goal_version_id=v.id)
    )
    ctx = _assemble(migrated_engine, person_id)
    carried = next(c for c in ctx.candidates if c.goal_id == g.id)
    assert carried.is_carry_over is True


@pytest.mark.integration
def test_quota_count_alias_keeps_quota_alive(
    migrated_engine, goal_repo, plan_repo, person_id
):
    """Prod ingestion wrote {"count": N}; the reader must not collapse it to
    1/week (volleyball 2x: one done session must NOT mark the quota met)."""
    g, v = _make_goal(
        goal_repo,
        person_id,
        "2x/week volleyball",
        recurrence=RecurrenceType.QUOTA,
        recurrence_config={"count": 2, "window": "week"},
    )
    # complete one session earlier in this quota window (yesterday)
    yplan = plan_repo.get_or_create_plan(person_id, YESTERDAY)
    item = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=yplan.id, goal_id=g.id, goal_version_id=v.id)
    )
    plan_repo.set_item_outcome(item.id, PlanItemStatus.DONE)
    ctx = _assemble(migrated_engine, person_id)
    # with count honored (2), one done session leaves the quota unmet → still due
    assert g.id in {c.goal_id for c in ctx.candidates}

"""B4 — goal-type mechanics, smart subset + heavy-day trim, log_progress.

Integration tests against the migrated Postgres DB (real repos + use-cases).
"""

from datetime import date, timedelta

import pytest
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
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from task_tracker.application.query_client import DailySignal

TODAY = date.today()


def _goal(
    goal_repo,
    person_id,
    title,
    recurrence,
    config=None,
    *,
    level=Level.NEED,
    target=None,
    unit=None,
    completion=CompletionType.BINARY,
):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title=title))
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=level,
            definition=title,
            version_no=1,
            recurrence_type=recurrence,
            recurrence_config=config or {},
            completion_type=completion,
            target_quantity=target,
            quantity_unit=unit,
        )
    )
    return g, v


def _assemble(engine, person_id, plan_date=TODAY, signal=None):
    return assemble_morning_context(
        person_id,
        plan_date,
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
        daily_signal=signal,
    )


def _uc(engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )


def _plan_with_item(plan_repo, person_id, goal, version, plan_date):
    plan = plan_repo.get_or_create_plan(person_id, plan_date)
    return plan_repo.add_plan_item(
        DailyPlanItem(
            daily_plan_id=plan.id, goal_id=goal.id, goal_version_id=version.id
        )
    )


# --- rotation --------------------------------------------------------------


@pytest.mark.integration
def test_rotation_current_item_and_advance_on_done(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _goal(
        goal_repo,
        person_id,
        "Split",
        RecurrenceType.ROTATION,
        {"sequence": ["upper", "lower", "rest"], "rest_labels": ["rest"]},
    )
    # current session is the first slot, and rotation is must-show
    ctx = _assemble(migrated_engine, person_id)
    item = next(c for c in ctx.candidates if c.goal_id == g.id)
    assert item.bucket == "must_show"
    assert goal_repo.get_goal_state(g.id).rotation_index in (None, 0)

    dpi = _plan_with_item(plan_repo, person_id, g, v, TODAY)
    _uc(migrated_engine).log_outcome(dpi.id, "done")
    # pointer advanced one slot on done
    assert goal_repo.get_goal_state(g.id).rotation_index == 1


@pytest.mark.integration
def test_rotation_miss_holds_pointer(migrated_engine, goal_repo, plan_repo, person_id):
    g, v = _goal(
        goal_repo,
        person_id,
        "Split",
        RecurrenceType.ROTATION,
        {"sequence": ["upper", "lower"]},
    )
    dpi = _plan_with_item(plan_repo, person_id, g, v, TODAY)
    _uc(migrated_engine).log_outcome(dpi.id, "not_done")
    # a miss never advances the pointer — the same item re-surfaces
    assert goal_repo.get_goal_state(g.id).rotation_index in (None, 0)


# --- interval --------------------------------------------------------------


@pytest.mark.integration
def test_interval_due_then_not_due_after_completion(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _goal(
        goal_repo, person_id, "Pushups", RecurrenceType.INTERVAL, {"every_days": 4}
    )
    # never completed → due today → surfaces
    ctx = _assemble(migrated_engine, person_id)
    assert any(c.goal_id == g.id for c in ctx.candidates)

    dpi = _plan_with_item(plan_repo, person_id, g, v, TODAY)
    _uc(migrated_engine).log_outcome(dpi.id, "done")
    assert goal_repo.get_goal_state(g.id).last_completed_at is not None

    # now inside the 4-day window → not due → not a candidate (still in full_list)
    ctx2 = _assemble(migrated_engine, person_id)
    assert not any(c.goal_id == g.id for c in ctx2.candidates)
    assert any(c.goal_id == g.id for c in ctx2.full_list)


# --- quota -----------------------------------------------------------------


@pytest.mark.integration
def test_quota_forced_when_behind_pace(migrated_engine, goal_repo, person_id):
    g, _ = _goal(
        goal_repo,
        person_id,
        "Gym",
        RecurrenceType.QUOTA,
        {"per_window": 3, "window": "week", "week_start": "monday"},
    )
    # Sunday (last day of the Mon-anchored window), 0 sessions done → forced
    sunday = date(2026, 7, 5)
    ctx = _assemble(migrated_engine, person_id, plan_date=sunday)
    item = next(c for c in ctx.candidates if c.goal_id == g.id)
    assert item.bucket == "forced"


@pytest.mark.integration
def test_quota_slack_is_suggested(migrated_engine, goal_repo, person_id):
    g, _ = _goal(
        goal_repo,
        person_id,
        "Gym",
        RecurrenceType.QUOTA,
        {"per_window": 3, "window": "week", "week_start": "monday"},
    )
    # Monday, full week ahead → slack → offered, not forced
    monday = date(2026, 6, 29)
    ctx = _assemble(migrated_engine, person_id, plan_date=monday)
    item = next(c for c in ctx.candidates if c.goal_id == g.id)
    assert item.bucket == "suggested"


# --- fixed_schedule --------------------------------------------------------


@pytest.mark.integration
def test_fixed_schedule_only_on_named_days(migrated_engine, goal_repo, person_id):
    g, _ = _goal(
        goal_repo, person_id, "Class", RecurrenceType.FIXED_SCHEDULE, {"weekdays": [4]}
    )  # Fridays only
    friday, thursday = date(2026, 7, 3), date(2026, 7, 2)
    assert any(
        c.goal_id == g.id
        for c in _assemble(migrated_engine, person_id, plan_date=friday).candidates
    )
    assert not any(
        c.goal_id == g.id
        for c in _assemble(migrated_engine, person_id, plan_date=thursday).candidates
    )


# --- accumulation ----------------------------------------------------------


@pytest.mark.integration
def test_accumulation_accrues_and_status_derives(migrated_engine, goal_repo, person_id):
    g, _ = _goal(
        goal_repo,
        person_id,
        "Painting",
        RecurrenceType.ACCUMULATION,
        {"window": "chapter"},
        target=4,
        unit="hours",
        completion=CompletionType.DURATION,
    )
    uc = _uc(migrated_engine)

    r1 = uc.log_progress(person_id, g.id, 1.5, on=TODAY, unit="hours")
    assert r1["total"] == 1.5
    assert r1["reached"] is False
    assert r1["item"]["status"] == PlanItemStatus.DONE  # status derives from progress

    r2 = uc.log_progress(person_id, g.id, 2.5, on=TODAY)
    assert r2["total"] == 4.0
    assert r2["reached"] is True

    # accumulation is exempt from miss semantics — never touched carry_over
    assert goal_repo.get_carry_over_count(g.id) == 0


@pytest.mark.integration
def test_accumulation_stops_surfacing_when_target_reached(
    migrated_engine, goal_repo, person_id
):
    g, _ = _goal(
        goal_repo,
        person_id,
        "Painting",
        RecurrenceType.ACCUMULATION,
        {"window": "chapter"},
        target=4,
        unit="hours",
        completion=CompletionType.DURATION,
    )
    uc = _uc(migrated_engine)
    assert any(
        c.goal_id == g.id for c in _assemble(migrated_engine, person_id).candidates
    )
    uc.log_progress(person_id, g.id, 4.0, on=TODAY)
    # target reached → no longer a prompt-to-engage
    assert not any(
        c.goal_id == g.id for c in _assemble(migrated_engine, person_id).candidates
    )


@pytest.mark.integration
def test_log_progress_rejects_non_accumulation(migrated_engine, goal_repo, person_id):
    g, _ = _goal(goal_repo, person_id, "Steps", RecurrenceType.DAILY, {})
    with pytest.raises(ValueError, match="accumulation"):
        _uc(migrated_engine).log_progress(person_id, g.id, 100, on=TODAY)


# --- heavy-day trim (D-12) -------------------------------------------------


@pytest.mark.integration
def test_heavy_day_trims_non_needs_but_keeps_every_need(
    migrated_engine, goal_repo, person_id
):
    needs = [
        _goal(goal_repo, person_id, f"Need {i}", RecurrenceType.DAILY)[0]
        for i in range(2)
    ]
    for i in range(5):
        _goal(
            goal_repo, person_id, f"Want {i}", RecurrenceType.ONEOFF, level=Level.WANT
        )

    normal = _assemble(
        migrated_engine, person_id, signal=DailySignal(date=TODAY, whoop_recovery=50)
    )
    heavy = _assemble(
        migrated_engine, person_id, signal=DailySignal(date=TODAY, whoop_recovery=30)
    )

    assert normal.heavy_day is False
    assert heavy.heavy_day is True

    n_suggested = len([c for c in normal.candidates if c.bucket == "suggested"])
    h_suggested = len([c for c in heavy.candidates if c.bucket == "suggested"])
    assert h_suggested < n_suggested  # heavy day cuts non-need candidates

    # every need survives the trim, on both days
    for ctx in (normal, heavy):
        present = {c.goal_id for c in ctx.candidates}
        for need in needs:
            assert need.id in present


# --- backdating restriction (mcp-tools §3.1/§5) ----------------------------


@pytest.mark.integration
def test_backdating_rejected_for_pointer_goal(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _goal(
        goal_repo, person_id, "Pushups", RecurrenceType.INTERVAL, {"every_days": 4}
    )
    yesterday = TODAY - timedelta(days=1)
    dpi = _plan_with_item(plan_repo, person_id, g, v, yesterday)
    with pytest.raises(ValueError, match="backdat"):
        _uc(migrated_engine).log_outcome(dpi.id, "done")


@pytest.mark.integration
def test_backdating_allowed_for_non_pointer_goal(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g, v = _goal(goal_repo, person_id, "Steps", RecurrenceType.DAILY)
    yesterday = TODAY - timedelta(days=1)
    dpi = _plan_with_item(plan_repo, person_id, g, v, yesterday)
    # non-pointer goals backdate freely
    out = _uc(migrated_engine).log_outcome(dpi.id, "done")
    assert out["status"] == PlanItemStatus.DONE

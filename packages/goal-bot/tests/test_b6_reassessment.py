"""B6 — reassessment lifecycle actions. Lead: the never-auto-drop guard.

Nothing leaves the system without an explicit user choice (non-negotiable 5).
"""

from datetime import date

import pytest
from goal_bot.application.morning_turn import _RITUAL_GRANT
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    Goal,
    GoalVersion,
    Level,
    RecurrenceType,
    VersionLifecycle,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.server import RITUAL_TOOL_DEFS

TODAY = date(2026, 6, 27)


def _make_goal(
    goal_repo,
    person_id,
    title,
    *,
    recurrence=RecurrenceType.DAILY,
    level=Level.NEED,
    target=None,
):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title=title))
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=level,
            definition=title,
            version_no=1,
            recurrence_type=recurrence,
            recurrence_config={},
            completion_type=CompletionType.BINARY,
            target_quantity=target,
        )
    )
    return g, v


def _uc(engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )


# --- the never-auto-drop guard (lead) --------------------------------------


@pytest.mark.integration
def test_threshold_crossing_never_writes_a_lifecycle_change(
    migrated_engine, goal_repo, person_id
):
    g, v = _make_goal(goal_repo, person_id, "Meditate")
    for _ in range(9):  # well past the reassessment threshold
        goal_repo.advance_carry_over(g.id)

    ctx = assemble_morning_context(
        person_id,
        TODAY,
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )
    assert ctx.reassessment is not None  # the nudge fires...

    # ...but NOTHING is dropped/paused/archived. The system only offered.
    goal, versions = goal_repo.get_goal_detail(g.id)
    assert goal.archived_at is None
    assert all(ver.lifecycle == VersionLifecycle.ACTIVE for ver in versions)


@pytest.mark.integration
def test_assemble_never_invokes_a_lifecycle_write(
    migrated_engine, goal_repo, person_id, monkeypatch
):
    g, _ = _make_goal(goal_repo, person_id, "Meditate")
    for _ in range(9):
        goal_repo.advance_carry_over(g.id)

    def _boom(*a, **k):
        raise AssertionError("a lifecycle write fired during assemble")

    for name in ("set_goal_archived", "set_versions_lifecycle", "set_rotation_pointer"):
        monkeypatch.setattr(SqlAlchemyGoalRepository, name, _boom)

    # assembling the offer must never touch a lifecycle write
    assemble_morning_context(
        person_id,
        TODAY,
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


# --- each offer path executes the right write on explicit choice ------------


@pytest.mark.integration
def test_re_anchor_creates_lower_version_keeps_goal_active(
    migrated_engine, goal_repo, person_id
):
    g, v1 = _make_goal(
        goal_repo, person_id, "Steps", recurrence=RecurrenceType.DAILY, target=8000
    )
    # user picks re-anchor → a new need version at the lower 95%-floor bar
    _uc(migrated_engine).create_goal_version(
        goal_id=g.id,
        level="need",
        definition="5k steps",
        recurrence_type="daily",
        recurrence_config={},
        completion_type="quantity",
        target_quantity=5000,
    )
    goal, versions = goal_repo.get_goal_detail(g.id)
    assert goal.archived_at is None  # goal stays active
    current = [ver for ver in versions if ver.effective_to is None]
    prior = [ver for ver in versions if ver.effective_to is not None]
    assert len(current) == 1 and current[0].target_quantity == 5000
    assert len(prior) == 1 and prior[0].id == v1.id  # prior version closed


@pytest.mark.integration
def test_pause_makes_versions_dormant_not_archived(
    migrated_engine, goal_repo, person_id
):
    g, _ = _make_goal(goal_repo, person_id, "Gym")
    _uc(migrated_engine).set_goal_lifecycle(g.id, "pause")
    goal, versions = goal_repo.get_goal_detail(g.id)
    assert all(ver.lifecycle == VersionLifecycle.PAUSED for ver in versions)
    assert goal.archived_at is None  # dormant, not dropped


@pytest.mark.integration
def test_activate_reverses_pause(migrated_engine, goal_repo, person_id):
    g, _ = _make_goal(goal_repo, person_id, "Gym")
    uc = _uc(migrated_engine)
    uc.set_goal_lifecycle(g.id, "pause")
    uc.set_goal_lifecycle(g.id, "activate")
    _, versions = goal_repo.get_goal_detail(g.id)
    assert all(ver.lifecycle == VersionLifecycle.ACTIVE for ver in versions)


@pytest.mark.integration
def test_retire_archives_and_unarchive_reverses(migrated_engine, goal_repo, person_id):
    g, _ = _make_goal(goal_repo, person_id, "Old goal")
    uc = _uc(migrated_engine)
    uc.set_goal_lifecycle(g.id, "archive")
    assert goal_repo.get_goal_detail(g.id)[0].archived_at is not None
    uc.set_goal_lifecycle(g.id, "unarchive")
    assert goal_repo.get_goal_detail(g.id)[0].archived_at is None


@pytest.mark.integration
def test_oneoff_drop_archives_on_explicit_choice(migrated_engine, goal_repo, person_id):
    g, _ = _make_goal(
        goal_repo, person_id, "Call the plumber", recurrence=RecurrenceType.ONEOFF
    )
    _uc(migrated_engine).set_goal_lifecycle(g.id, "archive")  # user chose drop
    assert goal_repo.get_goal_detail(g.id)[0].archived_at is not None


def test_set_goal_lifecycle_rejects_unknown_state(migrated_engine, person_id):
    with pytest.raises(ValueError, match="archive"):
        _uc(migrated_engine).set_goal_lifecycle(1, "delete")


# --- set_rotation_pointer: explicit, no side effects ------------------------


@pytest.mark.integration
def test_set_rotation_pointer_sets_pointer_no_completion(
    migrated_engine, goal_repo, person_id
):
    g, _ = _make_goal(goal_repo, person_id, "Split", recurrence=RecurrenceType.ROTATION)
    _uc(migrated_engine).set_rotation_pointer(g.id, 2)
    state = goal_repo.get_goal_state(g.id)
    assert state.rotation_index == 2
    assert state.last_completed_at is None  # no completion attached


@pytest.mark.integration
def test_log_outcome_never_calls_set_rotation_pointer(
    migrated_engine, goal_repo, plan_repo, person_id, monkeypatch
):
    from goal_bot.domain.entities import DailyPlanItem

    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="Split"))
    # a rotation goal with a real sequence so advance has something to step
    gv = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=Level.NEED,
            definition="seq",
            version_no=1,
            recurrence_type=RecurrenceType.ROTATION,
            recurrence_config={"sequence": ["a", "b"]},
            completion_type=CompletionType.BINARY,
        )
    )
    # today-dated so the B4 backdating guard doesn't fire
    plan = plan_repo.get_or_create_plan(person_id, date.today())
    item = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=g.id, goal_version_id=gv.id)
    )

    def _boom(*a, **k):
        raise AssertionError("log_outcome implicitly nudged the pointer")

    monkeypatch.setattr(SqlAlchemyGoalRepository, "set_rotation_pointer", _boom)
    # completion advances via advance_rotation, NEVER set_rotation_pointer
    _uc(migrated_engine).log_outcome(item.id, "done")
    assert goal_repo.get_goal_state(g.id).rotation_index == 1  # advanced one slot


# --- grant exposure ---------------------------------------------------------


def test_lifecycle_tools_in_ritual_grant():
    for name in ("set_goal_lifecycle", "set_rotation_pointer", "create_goal_version"):
        assert name in _RITUAL_GRANT
        assert any(d["name"] == name for d in RITUAL_TOOL_DEFS)

"""ADR-0016 — rotation groups: cadence scheduled across member goals.

Lead: the push/rest/pull/rest scenario from local testing. Members keep their
own bars and logging; the group owns the shared pointer; exactly one member
can surface per day; a miss holds the pointer and shifts everything downstream.

Dates are relative to date.today() (D0) because log_outcome's backdating gate
and the group walk both key off the item's plan_date vs. the real clock.
"""

from datetime import date, timedelta

import pytest
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    Goal,
    GoalVersion,
    Level,
    RecurrenceType,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository

D0 = date.today()  # "Friday" in the motivating scenario
D1, D2, D3 = (D0 + timedelta(days=n) for n in (1, 2, 3))


def _uc(engine) -> GoalUseCases:
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )


def _make_interval_goal(goal_repo, person_id, title, target):
    """A member goal exactly like the seeded pushups/pull-ups: interval config
    stays on the version (inert while grouped — graceful degradation)."""
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title=title))
    goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            version_no=1,
            level=Level.NEED,
            definition=f"{target} {title}, every 4 days",
            recurrence_type=RecurrenceType.INTERVAL,
            recurrence_config={"every_days": 4},
            completion_type=CompletionType.QUANTITY,
            target_quantity=target,
        )
    )
    return g


def _push_pull(goal_repo, person_id, uc):
    push = _make_interval_goal(goal_repo, person_id, "pushups", 50)
    pull = _make_interval_goal(goal_repo, person_id, "pull-ups", 20)
    group = uc.create_rotation_group(
        person_id,
        "calisthenics",
        [
            {"goal_id": push.id},
            {"rest": True},
            {"goal_id": pull.id},
            {"rest": True},
        ],
    )
    return push, pull, group


def _due_titles(engine, person_id, on) -> set[str]:
    ctx = assemble_morning_context(
        person_id,
        on,
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )
    return {c.goal_title for c in ctx.candidates}


def _log(engine, plan_repo, person_id, goal, on, status, qty=None):
    detail = SqlAlchemyGoalRepository(engine).get_goal_detail(goal.id)
    version_id = detail[1][0].id
    plan = plan_repo.get_or_create_plan(person_id, on)
    item = plan_repo.get_or_create_item(plan.id, goal.id, version_id)
    return _uc(engine).log_outcome(item.id, status, qty)


# --- the motivating scenario -------------------------------------------------


@pytest.mark.integration
def test_only_one_member_surfaces_never_both(migrated_engine, goal_repo, person_id):
    # The original failure: two interval goals drifted into phase and both
    # surfaced the same day. Grouped, exactly one member can be due.
    uc = _uc(migrated_engine)
    _push_pull(goal_repo, person_id, uc)
    due = _due_titles(migrated_engine, person_id, D0)
    assert "pushups" in due
    assert "pull-ups" not in due


@pytest.mark.integration
def test_push_friday_rest_saturday_pull_sunday(
    migrated_engine, goal_repo, plan_repo, person_id
):
    uc = _uc(migrated_engine)
    push, pull, _ = _push_pull(goal_repo, person_id, uc)

    _log(migrated_engine, plan_repo, person_id, push, D0, "done", 50)

    saturday = _due_titles(migrated_engine, person_id, D1)
    assert "pushups" not in saturday and "pull-ups" not in saturday  # rest day

    sunday = _due_titles(migrated_engine, person_id, D2)
    assert "pull-ups" in sunday
    assert "pushups" not in sunday


@pytest.mark.integration
def test_missed_push_shifts_pull_too(migrated_engine, goal_repo, plan_repo, person_id):
    uc = _uc(migrated_engine)
    push, pull, _ = _push_pull(goal_repo, person_id, uc)

    # Friday passes with no done (silence or engaged not_done — either way the
    # pointer holds). Saturday is still a push day; pull waits behind it.
    _log(migrated_engine, plan_repo, person_id, push, D0, "not_done")
    saturday = _due_titles(migrated_engine, person_id, D1)
    assert "pushups" in saturday
    assert "pull-ups" not in saturday

    # Push done Saturday → Sunday rest → pull Monday.
    _log(migrated_engine, plan_repo, person_id, push, D1, "done", 50)
    assert _due_titles(migrated_engine, person_id, D2).isdisjoint(
        {"pushups", "pull-ups"}
    )
    assert "pull-ups" in _due_titles(migrated_engine, person_id, D3)


@pytest.mark.integration
def test_group_pointer_advances_from_surfaced_entry(
    migrated_engine, goal_repo, plan_repo, person_id
):
    # Bug-2 regression at the group level: after push (ptr → rest slot 1),
    # completing pull must set the pointer to 3 (one past pull's slot 2) —
    # advancing from the stored pointer would land on 2 and surface pull twice.
    uc = _uc(migrated_engine)
    push, pull, group = _push_pull(goal_repo, person_id, uc)

    _log(migrated_engine, plan_repo, person_id, push, D0, "done", 50)
    assert goal_repo.get_rotation_group(group["id"]).rotation_index == 1

    _log(migrated_engine, plan_repo, person_id, pull, D2, "done", 20)
    assert goal_repo.get_rotation_group(group["id"]).rotation_index == 3


@pytest.mark.integration
def test_silence_changes_no_group_state(migrated_engine, goal_repo, person_id):
    # NULL-TOLERANCE, structurally: assembling day after day with no outcome
    # logged never moves the pointer or stamps a completion.
    uc = _uc(migrated_engine)
    _, _, group = _push_pull(goal_repo, person_id, uc)
    for on in (D0, D1, D2, D3):
        _due_titles(migrated_engine, person_id, on)
    g = goal_repo.get_rotation_group(group["id"])
    assert g.rotation_index == 0
    assert g.last_completed_at is None


# --- membership rules ---------------------------------------------------------


@pytest.mark.integration
def test_member_may_have_one_scheduler_only(migrated_engine, goal_repo, person_id):
    uc = _uc(migrated_engine)
    push, _, _ = _push_pull(goal_repo, person_id, uc)
    with pytest.raises(ValueError, match="one scheduler"):
        uc.create_rotation_group(person_id, "dupe", [{"goal_id": push.id}])


@pytest.mark.integration
def test_create_rejects_malformed_and_foreign(migrated_engine, goal_repo, person_id):
    uc = _uc(migrated_engine)
    g = _make_interval_goal(goal_repo, person_id, "solo", 1)
    with pytest.raises(ValueError, match="entries must be"):
        uc.create_rotation_group(person_id, "bad", [{"label": "push"}])
    with pytest.raises(ValueError, match="at least one member"):
        uc.create_rotation_group(person_id, "bad", [{"rest": True}])
    with pytest.raises(ValueError, match="no goal"):
        uc.create_rotation_group(person_id, "bad", [{"goal_id": g.id + 999}])


@pytest.mark.integration
def test_archived_group_members_degrade_to_self_scheduling(
    migrated_engine, goal_repo, person_id
):
    # Members keep their own (inert) interval config; archive the group and
    # they fall back to it — both due immediately (never completed).
    uc = _uc(migrated_engine)
    _, _, group = _push_pull(goal_repo, person_id, uc)
    uc.archive_rotation_group(group["id"])
    due = _due_titles(migrated_engine, person_id, D0)
    assert {"pushups", "pull-ups"} <= due


# --- label rotation (single goal) — the two spec-§5 bug fixes ------------------


@pytest.mark.integration
def test_label_rotation_rest_consumes_a_day_and_advances_from_surfaced(
    migrated_engine, goal_repo, plan_repo, person_id
):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="split"))
    goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            version_no=1,
            level=Level.NEED,
            definition="upper/lower split",
            recurrence_type=RecurrenceType.ROTATION,
            recurrence_config={
                "sequence": ["upper", "rest", "lower", "rest"],
                "rest_labels": ["rest"],
            },
            completion_type=CompletionType.BINARY,
        )
    )

    assert "split" in _due_titles(migrated_engine, person_id, D0)
    _log(migrated_engine, plan_repo, person_id, g, D0, "done")

    # Bug 1: the old walk offered the next session the very next day.
    assert "split" not in _due_titles(migrated_engine, person_id, D1)
    assert "split" in _due_titles(migrated_engine, person_id, D2)

    # Bug 2: completing the session surfaced past a rest slot must advance
    # from the surfaced index (2 → 3), not stored+1 (1 → 2 = same session).
    _log(migrated_engine, plan_repo, person_id, g, D2, "done")
    assert goal_repo.get_goal_state(g.id).rotation_index == 3

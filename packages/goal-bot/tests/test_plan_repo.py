from datetime import date

import pytest
from goal_bot.domain.entities import (
    CompletionType,
    DailyPlanItem,
    Goal,
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
)

TODAY = date(2026, 6, 27)


def _setup_goal(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="test"))
    v = goal_repo.create_goal_version(GoalVersion(
        goal_id=g.id,
        version_no=1,
        level=Level.NEED,
        definition="bar",
        recurrence_type=RecurrenceType.DAILY,
        recurrence_config={},
        completion_type=CompletionType.BINARY,
    ))
    return g, v


@pytest.mark.integration
def test_get_or_create_plan_idempotent(plan_repo, person_id):
    p1 = plan_repo.get_or_create_plan(person_id, TODAY)
    p2 = plan_repo.get_or_create_plan(person_id, TODAY)
    assert p1.id == p2.id
    assert p1.person_id == person_id
    assert p1.plan_date == TODAY


@pytest.mark.integration
def test_add_plan_item_pins_version(goal_repo, plan_repo, person_id):
    g, v = _setup_goal(goal_repo, person_id)
    plan = plan_repo.get_or_create_plan(person_id, TODAY)

    item = plan_repo.add_plan_item(DailyPlanItem(
        daily_plan_id=plan.id,
        goal_id=g.id,
        goal_version_id=v.id,
    ))
    assert item.id is not None
    assert item.goal_version_id == v.id
    assert item.status == PlanItemStatus.PLANNED


@pytest.mark.integration
def test_set_item_outcome_not_done(goal_repo, plan_repo, person_id):
    g, v = _setup_goal(goal_repo, person_id)
    plan = plan_repo.get_or_create_plan(person_id, TODAY)
    item = plan_repo.add_plan_item(DailyPlanItem(
        daily_plan_id=plan.id, goal_id=g.id, goal_version_id=v.id,
    ))

    updated = plan_repo.set_item_outcome(item.id, PlanItemStatus.NOT_DONE)
    assert updated.status == PlanItemStatus.NOT_DONE


@pytest.mark.integration
def test_lock_in_sets_explicit_flag(goal_repo, plan_repo, person_id):
    plan = plan_repo.get_or_create_plan(person_id, TODAY)
    locked = plan_repo.lock_in(plan.id, explicit=True)
    assert locked.lock_was_explicit is True
    assert locked.locked_in_at is not None


@pytest.mark.integration
def test_get_plan_for_date_round_trip(goal_repo, plan_repo, person_id):
    g, v = _setup_goal(goal_repo, person_id)
    plan = plan_repo.get_or_create_plan(person_id, TODAY)
    plan_repo.add_plan_item(DailyPlanItem(
        daily_plan_id=plan.id, goal_id=g.id, goal_version_id=v.id,
    ))

    result = plan_repo.get_plan_for_date(person_id, TODAY)
    assert result is not None
    fetched_plan, items = result
    assert fetched_plan.id == plan.id
    assert len(items) == 1
    assert items[0].goal_id == g.id

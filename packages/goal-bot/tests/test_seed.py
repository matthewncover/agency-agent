from datetime import date

import pytest
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.seed import seed_demo

TODAY = date.today()


@pytest.mark.integration
def test_seed_returns_person_id(migrated_engine):
    pid = seed_demo(migrated_engine)
    assert isinstance(pid, int)
    assert pid > 0


@pytest.mark.integration
def test_seed_full_goal_list_has_four_or_more(migrated_engine):
    pid = seed_demo(migrated_engine)
    uc = GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )
    goals = uc.get_full_goal_list(pid, TODAY)
    assert len(goals) >= 4


@pytest.mark.integration
def test_seed_chapter_less_goal_in_list(migrated_engine):
    pid = seed_demo(migrated_engine)
    uc = GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )
    goals = uc.get_full_goal_list(pid, TODAY)
    assert any(g["chapter_id"] is None for g in goals)


@pytest.mark.integration
def test_seed_one_goal_has_both_need_and_want(migrated_engine):
    pid = seed_demo(migrated_engine)
    uc = GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )
    goals = uc.get_full_goal_list(pid, TODAY)
    for goal in goals:
        detail = uc.get_goal_detail(goal["id"])
        levels = {v["level"] for v in detail["versions"]}
        if "need" in levels and "want" in levels:
            return  # found it
    pytest.fail("no goal has both need and want versions")

from datetime import date

import pytest
from fakes import FakeLLM
from goal_bot.application.llm_port import LLMResponse, ToolCall
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import MorningTurn
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import PlanItemStatus
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.seed import seed_demo

TODAY = date(2026, 6, 27)


def _build_service(migrated_engine, fake: FakeLLM) -> MorningService:
    goals = SqlAlchemyGoalRepository(migrated_engine)
    plans = SqlAlchemyPlanRepository(migrated_engine)
    wins = SqlAlchemyWinRepository(migrated_engine)
    uc = GoalUseCases(goals=goals, plans=plans, wins=wins)
    turn = MorningTurn(llm=fake, uc=uc, tool_defs=[])
    return MorningService(goals=goals, plans=plans, wins=wins, turn=turn)


@pytest.mark.integration
def test_fire_morning_creates_plan_and_returns_session(migrated_engine):
    pid = seed_demo(migrated_engine)
    fake = FakeLLM([LLMResponse(text="Good morning! Yesterday you moved — that anchors everything.")])
    service = _build_service(migrated_engine, fake)

    session = service.fire_morning(pid, TODAY)

    plans_repo = SqlAlchemyPlanRepository(migrated_engine)
    result = plans_repo.get_plan_for_date(pid, TODAY)
    assert result is not None
    _, items = result
    assert len(items) >= 1
    assert all(i.status == PlanItemStatus.PLANNED for i in items)
    assert session.response_text != ""


@pytest.mark.integration
def test_handle_reply_persists_done(migrated_engine):
    pid = seed_demo(migrated_engine)
    plans_repo = SqlAlchemyPlanRepository(migrated_engine)

    # Fire morning to create the provisional plan
    fake_start = FakeLLM([LLMResponse(text="Morning!")])
    service = _build_service(migrated_engine, fake_start)
    session = service.fire_morning(pid, TODAY)

    result = plans_repo.get_plan_for_date(pid, TODAY)
    assert result is not None
    _, items = result
    first_item_id = items[0].id

    # Build a second service with FakeLLM scripted for the reply turn
    fake_reply = FakeLLM([
        LLMResponse(text="", tool_calls=[
            ToolCall(id="tc1", name="log_outcome", args={"daily_plan_item_id": first_item_id, "status": "done"})
        ]),
        LLMResponse(text="Logged!"),
    ])
    service2 = _build_service(migrated_engine, fake_reply)
    session = service2.handle_reply(session, "did the 20-min move")

    _, updated = plans_repo.get_plan_for_date(pid, TODAY)
    done = next(i for i in updated if i.id == first_item_id)
    assert done.status == PlanItemStatus.DONE


@pytest.mark.integration
def test_re_fire_morning_is_idempotent(migrated_engine):
    pid = seed_demo(migrated_engine)
    plans_repo = SqlAlchemyPlanRepository(migrated_engine)

    fake = FakeLLM([
        LLMResponse(text="Morning 1!"),
        LLMResponse(text="Morning 2!"),
    ])
    service = _build_service(migrated_engine, fake)

    service.fire_morning(pid, TODAY)
    _, items1 = plans_repo.get_plan_for_date(pid, TODAY)
    count1 = len(items1)

    service.fire_morning(pid, TODAY)
    _, items2 = plans_repo.get_plan_for_date(pid, TODAY)
    count2 = len(items2)

    assert count1 == count2  # no duplicate items on second fire

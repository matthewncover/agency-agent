from datetime import date

import pytest
from fakes import FakeLLM
from goal_bot.application.llm_port import LLMResponse, ToolCall
from goal_bot.application.morning_context import MorningContext
from goal_bot.application.morning_turn import MorningTurn
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

TODAY = date(2026, 6, 27)

_VKW = dict(
    version_no=1,
    recurrence_type=RecurrenceType.DAILY,
    recurrence_config={},
    completion_type=CompletionType.BINARY,
)


def _make_turn(migrated_engine, fake: FakeLLM) -> MorningTurn:
    uc = GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )
    return MorningTurn(llm=fake, uc=uc, tool_defs=[])


def _empty_ctx(person_id: int) -> MorningContext:
    return MorningContext(
        person_id=person_id,
        plan_date=TODAY,
        win_surface=[],
        thin_day=True,
        yesterday=[],
        candidates=[],
        full_list=[],
    )


@pytest.mark.integration
def test_win_leads_no_premature_tools(migrated_engine, person_id):
    fake = FakeLLM(
        [
            LLMResponse(
                text="Good morning! Yesterday you moved — that anchors everything."
            )
        ]
    )
    turn = _make_turn(migrated_engine, fake)

    session = turn.start(_empty_ctx(person_id))

    assert "Good morning" in session.response_text
    assert fake.call_count == 1  # one LLM call, no tool dispatch loop


@pytest.mark.integration
def test_report_done(migrated_engine, person_id, goal_repo, plan_repo):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="Move"))
    v = goal_repo.create_goal_version(
        GoalVersion(goal_id=g.id, level=Level.NEED, definition="20 min", **_VKW)
    )
    plan = plan_repo.get_or_create_plan(person_id, TODAY)
    item = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=g.id, goal_version_id=v.id)
    )

    fake = FakeLLM(
        [
            LLMResponse(text="Morning! Ready to move?"),
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="log_outcome",
                        args={"daily_plan_item_id": item.id, "status": "done"},
                    )
                ],
            ),
            LLMResponse(text="Logged — good work."),
        ]
    )
    turn = _make_turn(migrated_engine, fake)

    session = turn.start(_empty_ctx(person_id))
    session = turn.reply(session, "did the run")

    items = plan_repo.get_plan_items(plan.id)
    assert any(i.id == item.id and i.status == PlanItemStatus.DONE for i in items)
    assert "Logged" in session.response_text


@pytest.mark.integration
def test_manual_win(migrated_engine, person_id, win_repo):
    fake = FakeLLM(
        [
            LLMResponse(text="Morning!"),
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc2",
                        name="add_win",
                        args={"owner": person_id, "text": "finished the chapter"},
                    )
                ],
            ),
            LLMResponse(text="Win saved."),
        ]
    )
    turn = _make_turn(migrated_engine, fake)

    session = turn.start(_empty_ctx(person_id))
    session = turn.reply(session, "I finished the chapter yesterday")

    wins = win_repo.list_wins(person_id)
    assert any(w.text == "finished the chapter" for w in wins)
    assert "Win saved" in session.response_text


@pytest.mark.integration
def test_null_tolerance_silence_produces_no_tool_calls(migrated_engine, person_id):
    fake = FakeLLM([LLMResponse(text="Morning!")])
    turn = _make_turn(migrated_engine, fake)

    session = turn.start(_empty_ctx(person_id))

    # user never replies — no further state change
    assert fake.call_count == 1
    assert session.response_text == "Morning!"


@pytest.mark.integration
def test_ungranted_tool_refused(migrated_engine, person_id):
    fake = FakeLLM(
        [
            LLMResponse(text="Morning!"),
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc3",
                        name="create_goal",
                        args={
                            "owner": person_id,
                            "title": "New goal",
                            "chapter_id": None,
                        },
                    )
                ],
            ),
            LLMResponse(text="OK, let me handle that differently."),
        ]
    )
    turn = _make_turn(migrated_engine, fake)

    session = turn.start(_empty_ctx(person_id))
    session = turn.reply(session, "add a new goal for me")

    # create_goal was in an ungranted tool — no goals should be in the DB
    goals = SqlAlchemyGoalRepository(migrated_engine).get_full_goal_list(
        person_id, TODAY
    )
    assert len(goals) == 0
    assert "OK" in session.response_text

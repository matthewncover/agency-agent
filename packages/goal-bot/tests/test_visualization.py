from datetime import date, datetime, timezone

import pytest
from fakes import FakeLLM
from goal_bot.application.llm_port import LLMResponse
from goal_bot.application.morning_context import (
    CandidateItem,
    MorningContext,
    SurfacedVisualization,
)
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import MorningTurn
from goal_bot.application.prompt import build_system_prompt
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.visualization_repo import (
    SqlAlchemyVisualizationRepository,
)
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.infrastructure.telegram_adapter import command_payload
from goal_bot.seed import seed_demo

TODAY = date(2026, 6, 27)


# --- command payload extraction (pure) ---


def test_command_payload_plain():
    assert command_payload("/visualize tomorrow I run at dawn") == (
        "tomorrow I run at dawn"
    )


def test_command_payload_with_bot_mention():
    assert command_payload("/visualize@goal_bot ship the draft") == "ship the draft"


def test_command_payload_preserves_newlines():
    text = "/visualize first the run,\nthen deep work until noon"
    assert command_payload(text) == "first the run,\nthen deep work until noon"


def test_command_payload_empty():
    assert command_payload("/visualize") == ""
    assert command_payload("/visualize   ") == ""


# --- prompt section ---

_CANDIDATE = CandidateItem(goal_id=1, goal_version_id=1, goal_title="Move", level="need")


def _ctx(viz: list[SurfacedVisualization] | None = None) -> MorningContext:
    return MorningContext(
        person_id=1,
        plan_date=TODAY,
        win_surface=[],
        thin_day=False,
        yesterday=[],
        candidates=[_CANDIDATE],
        full_list=[_CANDIDATE],
        visualizations=viz or [],
    )


def test_prompt_omits_visualization_section_when_empty():
    prompt = build_system_prompt(_ctx())
    assert "visualization" not in prompt.lower()


def test_prompt_surfaces_visualization_verbatim():
    viz = [
        SurfacedVisualization(
            text="tomorrow I run at dawn",
            captured_at=datetime(2026, 6, 26, 21, 30, tzinfo=timezone.utc),
        )
    ]
    prompt = build_system_prompt(_ctx(viz))
    assert "tomorrow I run at dawn" in prompt
    lower = prompt.lower()
    # their words, given back — never rewritten, never converted into pressure
    assert "never rewrite" in lower
    assert "never a" in lower and "miss" in lower
    assert "wins still lead" in lower


# --- repo (integration) ---


@pytest.mark.integration
def test_claim_marks_surfaced_and_never_resurfaces(migrated_engine, person_id):
    repo = SqlAlchemyVisualizationRepository(migrated_engine)
    repo.add_visualization(person_id, "first: the run")
    repo.add_visualization(person_id, "second: actually, swim instead")

    claimed = repo.claim_unsurfaced(person_id, TODAY)
    assert [v.text for v in claimed] == [
        "first: the run",
        "second: actually, swim instead",
    ]
    assert all(v.surfaced_on == TODAY for v in claimed)

    # consume-on-read: a re-fire sees nothing
    assert repo.claim_unsurfaced(person_id, TODAY) == []


@pytest.mark.integration
def test_claim_is_per_person(migrated_engine, person_id):
    from agency_profile.domain.entities import Person
    from agency_profile.infrastructure.adapters.profile_repo import (
        SqlAlchemyProfileRepository,
    )

    other = (
        SqlAlchemyProfileRepository(migrated_engine)
        .create_person(Person(display_name="o", timezone="America/Los_Angeles"))
        .profile_id
    )
    repo = SqlAlchemyVisualizationRepository(migrated_engine)
    repo.add_visualization(person_id, "mine")

    assert repo.claim_unsurfaced(other, TODAY) == []
    assert [v.text for v in repo.claim_unsurfaced(person_id, TODAY)] == ["mine"]


# --- morning flow (integration) ---


def _build_service(migrated_engine, fake: FakeLLM) -> MorningService:
    goals = SqlAlchemyGoalRepository(migrated_engine)
    plans = SqlAlchemyPlanRepository(migrated_engine)
    wins = SqlAlchemyWinRepository(migrated_engine)
    uc = GoalUseCases(goals=goals, plans=plans, wins=wins)
    turn = MorningTurn(llm=fake, uc=uc, tool_defs=[])
    return MorningService(
        goals=goals,
        plans=plans,
        wins=wins,
        turn=turn,
        visualizations=SqlAlchemyVisualizationRepository(migrated_engine),
    )


@pytest.mark.integration
def test_visualization_reaches_morning_context_once(migrated_engine):
    pid = seed_demo(migrated_engine)
    fake = FakeLLM([LLMResponse(text="Morning 1"), LLMResponse(text="Morning 2")])
    service = _build_service(migrated_engine, fake)

    assert service.record_visualization(pid, "tomorrow I run at dawn")

    session = service.fire_morning(pid, TODAY)
    assert [v.text for v in session.ctx.visualizations] == ["tomorrow I run at dawn"]

    # second fire same day (manual /morning after the scheduled one): consumed
    session2 = service.fire_morning(pid, TODAY)
    assert session2.ctx.visualizations == []


def test_record_visualization_degrades_without_store():
    service = MorningService(goals=None, plans=None, wins=None, turn=None)
    assert service.record_visualization(1, "anything") is False

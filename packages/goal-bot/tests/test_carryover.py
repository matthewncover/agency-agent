"""B3 — carry-over counter & reassessment nudge (the live invariants).

These are the spec's load-bearing tests: INV-1 (NULL-TOLERANCE) and INV-2
(ENGAGEMENT-NOT-FAILURE) stop being "structural by absence" here and become
live machinery. Every assertion is deliberate.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fakes import FakeLLM
from goal_bot.application.llm_port import LLMResponse
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import MorningTurn
from goal_bot.application.prompt import build_system_prompt
from goal_bot.application.ritual_assembly import (
    _REASSESS_THRESHOLD,
    assemble_morning_context,
)
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    DailyPlanItem,
    Level,
    PlanItemStatus,
    RecurrenceType,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository

TODAY = date(2026, 6, 27)
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
def uc(migrated_engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


def _make_goal(uc, person_id, title, *, recurrence=RecurrenceType.DAILY):
    gid = uc.create_goal(person_id, title, chapter_id=None)
    vid = uc.create_goal_version(
        goal_id=gid,
        level=Level.NEED,
        definition=title,
        recurrence_type=recurrence,
        recurrence_config={},
        completion_type=CompletionType.BINARY,
    )
    return gid, vid


def _add_item(uc, person_id, gid, vid, on=TODAY):
    plan = uc.plans.get_or_create_plan(person_id, on)
    return uc.plans.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=gid, goal_version_id=vid)
    )


def _assemble(migrated_engine, person_id, on=TODAY):
    return assemble_morning_context(
        person_id,
        on,
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


# ── Test 1 ── not_done advances by exactly 1; done/partial do not ───────────
@pytest.mark.integration
def test_not_done_advances_by_one_done_partial_do_not(uc, person_id):
    gid, vid = _make_goal(uc, person_id, "Run")
    assert uc.goals.get_carry_over_count(gid) == 0

    uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
    assert uc.goals.get_carry_over_count(gid) == 1

    uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
    assert uc.goals.get_carry_over_count(gid) == 2

    # partial is not a miss — counter untouched
    uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "partial")
    assert uc.goals.get_carry_over_count(gid) == 2


# ── Test 2 ── silence NEVER advances the counter (INV-1) ────────────────────
@pytest.mark.integration
def test_planned_silence_never_advances_counter(uc, person_id):
    gid, vid = _make_goal(uc, person_id, "Meditate")

    # Multiple days of a planned item that is never answered → no tool call
    # ever fires, so the counter cannot move. Assert across several days.
    for offset in range(5):
        _add_item(uc, person_id, gid, vid, on=TODAY - timedelta(days=offset))
        assert uc.goals.get_carry_over_count(gid) == 0

    assert uc.goals.get_carry_over_count(gid) == 0


# ── Test 3 ── done resets/halts the chain for that goal ─────────────────────
@pytest.mark.integration
def test_done_resets_chain(uc, person_id):
    gid, vid = _make_goal(uc, person_id, "Read")

    for _ in range(3):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
    assert uc.goals.get_carry_over_count(gid) == 3

    uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "done")
    assert uc.goals.get_carry_over_count(gid) == 0


# ── Test 4 ── accumulation goals are exempt entirely (§4.3) ─────────────────
@pytest.mark.integration
def test_accumulation_goal_is_exempt(uc, migrated_engine, person_id):
    gid, vid = _make_goal(
        uc, person_id, "Paint", recurrence=RecurrenceType.ACCUMULATION
    )

    # Even repeated engaged not_done reports never advance the counter — an
    # accumulation goal has no per-day pass/fail.
    for _ in range(_REASSESS_THRESHOLD + 2):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
    assert uc.goals.get_carry_over_count(gid) == 0

    ctx = _assemble(migrated_engine, person_id)
    assert ctx.reassessment is None


# ── Test 5 ── threshold: fires at ~7 engaged misses, not at 6; only engaged
#             misses count toward it ────────────────────────────────────────
@pytest.mark.integration
def test_threshold_fires_at_seven(uc, migrated_engine, person_id):
    gid, vid = _make_goal(uc, person_id, "Write")
    for _ in range(_REASSESS_THRESHOLD):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")

    ctx = _assemble(migrated_engine, person_id)
    assert ctx.reassessment is not None
    assert ctx.reassessment.goal_id == gid
    assert ctx.reassessment.goal_type == "recurring"
    assert ctx.reassessment.offers == ["re_anchor", "retire_redirect", "pause"]


@pytest.mark.integration
def test_threshold_does_not_fire_at_six(uc, migrated_engine, person_id):
    gid, vid = _make_goal(uc, person_id, "Write")
    for _ in range(_REASSESS_THRESHOLD - 1):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")

    ctx = _assemble(migrated_engine, person_id)
    assert ctx.reassessment is None


@pytest.mark.integration
def test_threshold_counts_only_engaged_misses(uc, migrated_engine, person_id):
    gid, vid = _make_goal(uc, person_id, "Write")

    # Six engaged misses interleaved with any amount of silence: the silent
    # items produce no tool call, so only the engaged six reach the counter.
    for _ in range(_REASSESS_THRESHOLD - 1):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
        _add_item(uc, person_id, gid, vid)  # a silent, unanswered item
        _add_item(uc, person_id, gid, vid)  # another

    assert uc.goals.get_carry_over_count(gid) == _REASSESS_THRESHOLD - 1
    assert _assemble(migrated_engine, person_id).reassessment is None

    # One more engaged miss tips it over — silence never contributed.
    uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")
    assert _assemble(migrated_engine, person_id).reassessment is not None


@pytest.mark.integration
def test_oneoff_goal_gets_oneoff_offer_set(uc, migrated_engine, person_id):
    gid, vid = _make_goal(
        uc, person_id, "Renew passport", recurrence=RecurrenceType.ONEOFF
    )
    for _ in range(_REASSESS_THRESHOLD):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")

    nudge = _assemble(migrated_engine, person_id).reassessment
    assert nudge is not None
    assert nudge.goal_type == "oneoff"
    assert nudge.offers == ["still_a_need", "move_to_want", "drop"]


# ── Test 6 ── the nudge payload carries NO count / no day-by-day ────────────
@pytest.mark.integration
def test_nudge_payload_has_no_miss_data(uc, migrated_engine, person_id):
    gid, vid = _make_goal(uc, person_id, "Write")
    for _ in range(_REASSESS_THRESHOLD):
        uc.log_outcome(_add_item(uc, person_id, gid, vid).id, "not_done")

    ctx = _assemble(migrated_engine, person_id)
    payload = ctx.reassessment.model_dump()

    # Exactly the offer-only fields — no count, no history, no day-by-day.
    assert set(payload) == {"goal_id", "goal_title", "goal_type", "offers"}
    assert "count" not in payload
    assert not any(
        isinstance(v, int) and v >= _REASSESS_THRESHOLD
        for k, v in payload.items()
        if k != "goal_id"
    )

    # And the count must not leak into the assembled prompt either.
    prompt = build_system_prompt(ctx)
    assert str(_REASSESS_THRESHOLD) not in prompt.split("Reassessment offer")[1]


# ── Test 7 ── guardrail: no "log your miss" path; silence never → not_done ──
def test_guardrail_no_log_your_miss_phrase():
    src = Path(__file__).resolve().parents[1] / "src" / "goal_bot"
    offenders = [
        p
        for p in src.rglob("*.py")
        if "log your miss" in p.read_text().lower()
        or "log_your_miss" in p.read_text().lower()
    ]
    assert not offenders, f"forbidden 'log your miss' path found in {offenders}"


@pytest.mark.integration
def test_silence_never_becomes_not_done_or_advances_counter(migrated_engine, person_id):
    """End-to-end: an unanswered item rolled through the morning flow becomes
    `carried_over` (presence tracking) — never `not_done` — and the counter
    stays at 0. INV-1 holds through the real service path."""
    goals = SqlAlchemyGoalRepository(migrated_engine)
    plans = SqlAlchemyPlanRepository(migrated_engine)
    wins = SqlAlchemyWinRepository(migrated_engine)
    uc = GoalUseCases(goals=goals, plans=plans, wins=wins)

    gid, vid = _make_goal(uc, person_id, "Meditate")
    yplan = plans.get_or_create_plan(person_id, YESTERDAY)
    yitem = plans.add_plan_item(
        DailyPlanItem(daily_plan_id=yplan.id, goal_id=gid, goal_version_id=vid)
    )  # unanswered — pure silence

    turn = MorningTurn(llm=FakeLLM([LLMResponse(text="Morning!")]), uc=uc, tool_defs=[])
    MorningService(goals=goals, plans=plans, wins=wins, turn=turn).fire_morning(
        person_id, TODAY
    )

    _, items = plans.get_plan_for_date(person_id, YESTERDAY)
    rolled = next(i for i in items if i.id == yitem.id)
    assert rolled.status == PlanItemStatus.CARRIED_OVER  # never not_done
    assert goals.get_carry_over_count(gid) == 0  # silence advanced nothing

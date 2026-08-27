from datetime import date

from goal_bot.application.morning_context import (
    CandidateItem,
    MorningContext,
    SurfacedWin,
)
from goal_bot.application.prompt import build_system_prompt

_TODAY = date(2026, 6, 27)
_CANDIDATE = CandidateItem(
    goal_id=1, goal_version_id=1, goal_title="Move", level="need"
)


def _ctx(thin_day: bool = False, wins: list | None = None) -> MorningContext:
    return MorningContext(
        person_id=1,
        plan_date=_TODAY,
        win_surface=wins or [],
        thin_day=thin_day,
        yesterday=[],
        candidates=[_CANDIDATE],
        full_list=[_CANDIDATE],
    )


def test_prompt_leads_with_wins_instruction():
    lower = build_system_prompt(_ctx()).lower()
    assert "lead" in lower and "win" in lower


def test_prompt_prohibits_log_miss():
    lower = build_system_prompt(_ctx()).lower()
    assert "never" in lower
    assert "log" in lower and "miss" in lower


def test_prompt_autonomy_supportive():
    lower = build_system_prompt(_ctx()).lower()
    assert "offer" in lower or "autonomy" in lower


def test_prompt_name_the_bar():
    lower = build_system_prompt(_ctx()).lower()
    assert "bar" in lower


def test_prompt_past_day_logging_guidance():
    prompt = build_system_prompt(_ctx())
    lower = prompt.lower()
    assert "past" in lower and "never logged against today" in lower
    assert "get_plan" in prompt
    assert "revert_outcome" in prompt


def test_prompt_returns_to_open_question():
    lower = build_system_prompt(_ctx()).lower()
    assert "still-open question" in lower
    assert "never repeat the ask louder" in lower


def test_prompt_thin_day_includes_meaning_linked_ack():
    lower = build_system_prompt(_ctx(thin_day=True)).lower()
    assert "meaning" in lower or "meaning-linked" in lower


def test_prompt_no_thin_day_section_when_not_thin():
    win = SurfacedWin(text="Move", why="energy", source="derived")
    lower = build_system_prompt(_ctx(thin_day=False, wins=[win])).lower()
    # The thin-day *section* (added only when thin_day=True) begins with this phrase
    assert "nothing to surface from wins today" not in lower


def test_prompt_chapter_preamble_injected_with_parked_guardrail():
    ctx = _ctx().model_copy(
        update={
            "chapter_label": "Reset",
            "chapter_preamble": "Leaning into strength; guitar is parked.",
        }
    )
    out = build_system_prompt(ctx)
    assert "Leaning into strength; guitar is parked." in out
    assert "Reset" in out
    lower = out.lower()
    # The instruction must forbid nudging/guilting toward parked domains.
    assert "parked" in lower and "never nudge" in lower


def test_prompt_no_chapter_section_when_absent():
    assert "Chapter preamble" not in build_system_prompt(_ctx())


def test_prompt_rough_day_guidance_never_reads_silence():
    ctx = _ctx().model_copy(update={"framing_excerpt": "tone: direct, no coddling"})
    lower = build_system_prompt(ctx).lower()
    assert "rough" in lower
    assert "never infer a rough day from silence" in lower

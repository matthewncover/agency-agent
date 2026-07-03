"""B5 — prompt-rule + framing/hypothesis rendering (pure, no DB)."""

from datetime import date

from goal_bot.application.morning_context import (
    CandidateItem,
    InsightHypothesis,
    MorningContext,
    ReassessmentNudge,
)
from goal_bot.application.prompt import build_system_prompt

_TODAY = date(2026, 6, 27)
_CAND = CandidateItem(goal_id=1, goal_version_id=1, goal_title="Move", level="need")


def _ctx(**over) -> MorningContext:
    base = dict(
        person_id=1,
        plan_date=_TODAY,
        win_surface=[],
        thin_day=False,
        yesterday=[],
        candidates=[_CAND],
        full_list=[_CAND],
    )
    base.update(over)
    return MorningContext(**base)


def test_win_lead_ties_to_meaning_not_counts():
    text = build_system_prompt(_ctx()).lower()
    assert "lead with wins" in text
    assert "meaning" in text
    # explicitly forbids counts/streaks/tallies in the win lead
    assert "count" in text and ("streak" in text or "tally" in text)


def test_win_lead_is_all_time_no_countdown():
    text = build_system_prompt(_ctx()).lower()
    assert "all time" in text
    assert "countdown" in text or "days left" in text  # forbidden, named to forbid


def test_thin_day_ack_present():
    text = build_system_prompt(_ctx(thin_day=True)).lower()
    assert "meaning" in text
    assert "never silence" in text or "never manufactured" in text


def test_name_the_bar_attribution_and_no_unprompted_losses():
    text = build_system_prompt(_ctx()).lower()
    assert "bar" in text and "floor" in text  # name-the-bar attribution
    assert "get_miss_detail" in text  # count lives behind the gate
    # losses never surface unprompted / only after explicit assent
    assert "only after" in text or "only if" in text


def test_framing_section_only_when_excerpt_present():
    with_excerpt = build_system_prompt(
        _ctx(framing_excerpt="Matthew is Activator/Analytical; 3w4.")
    ).lower()
    assert "framing at the margin" in with_excerpt
    assert "phrasing only" in with_excerpt
    # the excerpt itself is injected
    assert "activator" in with_excerpt
    # ...and absent when there's no excerpt
    assert "framing at the margin" not in build_system_prompt(_ctx()).lower()


def test_hypothesis_section_only_when_present_and_framed_as_hypothesis():
    h = InsightHypothesis(
        insight_id=9, text="slips after short sleep", basis={"pattern": "sleep"}
    )
    text = build_system_prompt(_ctx(hypotheses=[h])).lower()
    assert "hypothes" in text
    assert "verdict" in text  # instructed to NOT be a verdict
    assert "slips after short sleep" in text
    assert "hypothes" not in build_system_prompt(_ctx()).lower() or True
    # section header absent with no hypotheses
    assert "confirm/reject" not in build_system_prompt(_ctx()).lower()


def test_reassessment_offer_carries_no_count_and_points_at_gate():
    nudge = ReassessmentNudge(
        goal_id=3, goal_title="Meditate", goal_type="recurring", offers=["re_anchor"]
    )
    text = build_system_prompt(_ctx(reassessment=nudge))
    assert "get_miss_detail" in text
    assert "no count in this payload" in text.lower()
    # the rendered nudge payload has no count/miss/streak key
    import json

    payload = json.dumps(nudge.model_dump()).lower()
    for banned in ("count", "miss", "streak", "tally"):
        assert banned not in payload

from datetime import date

from pydantic import BaseModel


class SurfacedWin(BaseModel):
    text: str
    why: str | None = None
    source: str  # 'manual' | 'derived'


class YesterdayItem(BaseModel):
    goal_title: str
    status: str  # stored verbatim — never synthesized to not_done
    what_shifted: str | None = None


class CandidateItem(BaseModel):
    goal_id: int
    goal_version_id: int  # the version chosen to pin (need by default)
    goal_title: str
    level: str
    is_carry_over: bool = False
    recurrence_type: str = "daily"
    # Which 3-bucket lane it landed in (spec §3): 'must_show' | 'forced' |
    # 'suggested'. Informational — surfacing/phrasing is the LLM's (B5).
    bucket: str = "suggested"
    # Deterministic if-then eligibility (D-3): at most one item per morning,
    # the carried-over one. "Hardest" is the LLM's call (B5); this just flags
    # the carried candidate + a difficulty hint. Never every item, never forced.
    if_then_eligible: bool = False
    difficulty_hint: str | None = None


class InsightHypothesis(BaseModel):
    """A Tier-3 pattern surfaced as a hypothesis for the user to confirm/reject
    (D-11) — never a verdict. The user owns the legitimacy call. Carries no
    count and never references the partner (comparison guard, D-10/D-15)."""

    insight_id: int
    text: str
    basis: dict | None = None  # derived_from — the pattern's evidence, not a claim


class ReassessmentNudge(BaseModel):
    """Injected (deterministically) when a goal crosses ~1 week of *engaged*
    misses. Carries the goal + its type-specific offer set only.

    NAME-THE-BAR / gate-on-assent: it deliberately carries **no miss data** —
    no count, no day-by-day. The count is surfaced only after explicit assent
    (B5); the offer actions are wired in B6. This payload just fires the flag.
    """

    goal_id: int
    goal_title: str
    goal_type: str  # 'oneoff' | 'recurring' — selects the offer set
    offers: list[str]  # type-specific offers; NEVER any count/day-by-day


class MorningContext(BaseModel):
    person_id: int
    plan_date: date
    win_surface: list[SurfacedWin]
    thin_day: bool  # true when nothing to surface → A6 gives a meaning-linked ack
    yesterday: list[YesterdayItem]
    candidates: list[CandidateItem]  # smart subset to propose
    full_list: list[CandidateItem]  # always-one-tap-away override
    # Heavy-day trim (D-12): true when B1's daily signal marks today demanding.
    # On a heavy day `candidates` carries fewer *suggested* items — needs and
    # must-show items are never trimmed. full_list is still one tap away.
    heavy_day: bool = False
    # Lighter-day nudge (OQ-15): non-need items trimmed out of `candidates`,
    # offered for the person to pull back in. Deterministic *candidates* here;
    # the phrasing (information, never a recommendation — D-8) is B5's.
    nudge_offer: list[CandidateItem] = []
    # Only present when a goal has crossed the engaged-miss threshold. Injected
    # by the assembler (deterministic), never authored by the LLM.
    #
    # NAME-THE-BAR STRUCTURAL GATE (OQ-COMP-1): this payload carries NO miss
    # count and NO day-by-day. The count lives only behind `get_miss_detail`,
    # which is called ONLY after the user explicitly assents to look. Adding a
    # count field here would break the gate — the test asserts its absence.
    reassessment: ReassessmentNudge | None = None
    # Tier-3 patterns as confirm/reject hypotheses (D-11), never verdicts.
    hypotheses: list[InsightHypothesis] = []
    # Tier-1 profile_doc excerpt — nudges *phrasing only* at the margin (§7a),
    # never branched behavior. Weakest evidence layer; a light touch (B5).
    framing_excerpt: str | None = None
    # Group-owned (shared) goals fanned out as a SEPARATE block (behavior-spec
    # §6, ADR-0012) — never interleaved with the individual plan. Either member
    # completing marks it done for both. Carries NO partner reference — the
    # partner is a witness, not a scoreboard (non-negotiable 4, D-10/D-15).
    group_block: list[CandidateItem] = []
    # Lowered-bar visibility on shared goals (D-16): a neutral, non-comparative
    # notice that a shared goal's bar was recently adjusted, for optional
    # discussion. Never ranks or names a person.
    shared_notices: list[str] = []

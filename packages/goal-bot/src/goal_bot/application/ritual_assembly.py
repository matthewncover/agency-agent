from dataclasses import dataclass
from datetime import date, timedelta

from task_tracker.application.query_client import DailySignal

from goal_bot.application.morning_context import (
    CandidateItem,
    InsightHypothesis,
    MorningContext,
    ReassessmentNudge,
    SurfacedVisualization,
    SurfacedWin,
    YesterdayItem,
)
from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.domain.entities import (
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
    VersionLifecycle,
)
from goal_bot.domain.recurrence import (
    QuotaStatus,
    accumulation_reached,
    fixed_schedule_is_due,
    interval_is_due,
    is_heavy_day,
    is_light_day,
    oneoff_is_due,
    quota_per_window,
    quota_status,
    quota_window_bounds,
    rotation_days_elapsed,
    rotation_due_index,
    rotation_group_due_goal_id,
    rotation_group_member_ids,
)

# Suggested-item caps (spec §3 "trim for realism"). Needs, must-show, forced
# quota, and carried-over commitments are never counted against these — only
# non-need *suggested* extras are trimmed. Heavy day → a tighter cap (D-12).
_SUGGESTED_CAP_NORMAL = 3
_SUGGESTED_CAP_HEAVY = 1

# Bucket labels (spec §3 three buckets).
_MUST_SHOW = "must_show"
_FORCED = "forced"
_SUGGESTED = "suggested"

# ~1 week of *engaged* misses before a reassessment nudge fires (behavior-spec
# §4). Silence never advances the counter, so only engaged `not_done` days ever
# reach this.
_REASSESS_THRESHOLD = 7

_ONEOFF_OFFERS = ["still_a_need", "move_to_want", "drop"]
_RECURRING_OFFERS = ["re_anchor", "retire_redirect", "pause"]


def _goal_type(recurrence: RecurrenceType) -> str:
    return "oneoff" if recurrence == RecurrenceType.ONEOFF else "recurring"


@dataclass
class _Classification:
    """The per-goal surfacing decision from the deterministic mechanics."""

    due: bool
    bucket: str  # _MUST_SHOW | _FORCED | _SUGGESTED (meaningful only when due)


def _classify(
    goal_id: int,
    version: GoalVersion,
    plan_date: date,
    goals: GoalRepositoryPort,
    plans: PlanRepositoryPort,
) -> _Classification:
    """Map a goal's current version + runtime state to (due?, which bucket),
    per recurrence type (spec §3/§5). Pure routing over recurrence.py."""
    rt = version.recurrence_type
    cfg = version.recurrence_config or {}

    if rt == RecurrenceType.DAILY:
        return _Classification(True, _MUST_SHOW)

    if rt == RecurrenceType.ROTATION:
        seq = cfg.get("sequence", [])
        state = goals.get_goal_state(goal_id)
        # Date-aware walk (ADR-0016): each consecutive rest label consumes one
        # elapsed day since completion — a rest day surfaces nothing.
        idx = rotation_due_index(
            seq,
            state.rotation_index,
            cfg.get("rest_labels"),
            rotation_days_elapsed(state.last_completed_at, plan_date),
        )
        return _Classification(idx is not None, _MUST_SHOW)

    if rt == RecurrenceType.INTERVAL:
        every = cfg.get("every_days", 1)
        due = interval_is_due(
            goals.get_goal_state(goal_id).last_completed_at, every, plan_date
        )
        return _Classification(due, _SUGGESTED)

    if rt == RecurrenceType.QUOTA:
        start, end = quota_window_bounds(plan_date, cfg.get("week_start", "monday"))
        done = plans.count_done_in_window(goal_id, start, end)
        status = quota_status(done, quota_per_window(cfg), plan_date, end)
        if status == QuotaStatus.MET:
            return _Classification(False, _SUGGESTED)
        if status == QuotaStatus.FORCED:
            return _Classification(True, _FORCED)
        return _Classification(True, _SUGGESTED)  # slack → offered, not forced

    if rt == RecurrenceType.FIXED_SCHEDULE:
        return _Classification(fixed_schedule_is_due(cfg, plan_date), _SUGGESTED)

    if rt == RecurrenceType.ACCUMULATION:
        total = plans.sum_progress(goal_id)
        return _Classification(
            not accumulation_reached(total, version.target_quantity), _SUGGESTED
        )

    # oneoff (and any unknown type): near/overdue target only (spec §3 bucket 3,
    # OQ-10). A no-target one-off never auto-surfaces — it stays one tap away in
    # the full list, and a carried-over one still surfaces via the carry-over
    # rule below. The pre-fix behavior (surface until done) buried the morning
    # under the errand pile — the overwhelm Jade's profile warns about.
    return _Classification(oneoff_is_due(cfg, plan_date), _SUGGESTED)


def assemble_morning_context(
    person_id: int,
    plan_date: date,
    goals: GoalRepositoryPort,
    plans: PlanRepositoryPort,
    wins: WinRepositoryPort,
    daily_signal: DailySignal | None = None,
    hypotheses: list[InsightHypothesis] | None = None,
    framing_excerpt: str | None = None,
    group_owner_ids: list[int] | None = None,
    visualizations: list[SurfacedVisualization] | None = None,
) -> MorningContext:
    # 1. Yesterday's plan
    yesterday_date = plan_date - timedelta(days=1)
    yesterday_result = plans.get_plan_for_date(person_id, yesterday_date)

    yesterday_out: list[YesterdayItem] = []
    carry_over_ids: set[int] = set()
    done_titles_why: list[tuple[str, str | None]] = []

    if yesterday_result:
        _, yitems = yesterday_result
        for item in yitems:
            detail = goals.get_goal_detail(item.goal_id)
            title = detail[0].title if detail else f"goal-{item.goal_id}"
            version_why: str | None = None
            if detail:
                for v in detail[1]:
                    if v.id == item.goal_version_id:
                        version_why = v.why
                        break

            yesterday_out.append(
                YesterdayItem(
                    goal_title=title,
                    status=item.status,
                    what_shifted=item.what_shifted,
                )
            )

            if item.status in {PlanItemStatus.DONE, PlanItemStatus.PARTIAL}:
                done_titles_why.append((title, version_why))
            else:
                # planned (unanswered) / not_done / carried_over → carry over
                carry_over_ids.add(item.goal_id)

    # 2. Win surface — derived first (recency), then manual; all-time; cap at 3
    derived = [
        SurfacedWin(text=title, why=why, source="derived")
        for title, why in done_titles_why
    ]
    manual = [
        SurfacedWin(text=w.text, why=None, source="manual")
        for w in wins.list_wins(person_id)
    ]
    win_surface = (derived + manual)[:3]
    thin_day = len(win_surface) == 0

    # 3. Today's eligible goals → classify each via the deterministic mechanics.
    today_goals = goals.get_full_goal_list(person_id, plan_date)

    # 3-pre. Rotation groups (ADR-0016): a goal referenced by an active group
    # is excluded from per-goal classification — the group is its sole
    # scheduler. Exactly one member per group can be due on a given day, so
    # same-day collisions are structurally impossible. (Distinct from the
    # group-PROFILE fan-out in step 7 — naming is unrelated.)
    active_goal_ids = {g.id for g in today_goals}
    rotation_member_ids: set[int] = set()
    rotation_due_ids: set[int] = set()
    for grp in goals.list_rotation_groups(person_id):
        rotation_member_ids.update(rotation_group_member_ids(grp.sequence))
        due_gid = rotation_group_due_goal_id(
            grp.sequence,
            grp.rotation_index,
            rotation_days_elapsed(grp.last_completed_at, plan_date),
            active_goal_ids,
        )
        if due_gid is not None:
            rotation_due_ids.add(due_gid)

    full_list: list[CandidateItem] = []
    protected: list[CandidateItem] = []  # needs + must-show + forced + carried
    trimmable: list[CandidateItem] = []  # non-need suggested extras
    reassess_candidates: list[tuple[int, ReassessmentNudge]] = []

    for goal in today_goals:
        detail = goals.get_goal_detail(goal.id)
        if not detail:
            continue
        _, versions = detail
        chosen = _pick_current_version(versions)
        if chosen is None:
            continue
        is_carry = goal.id in carry_over_ids
        carry_count = goals.get_carry_over_count(goal.id)

        item = CandidateItem(
            goal_id=goal.id,
            goal_version_id=chosen.id,
            goal_title=goal.title,
            level=str(chosen.level),
            is_carry_over=is_carry,
            recurrence_type=str(chosen.recurrence_type),
        )
        full_list.append(item)

        if goal.id in rotation_member_ids:
            # Group member: due iff the shared pointer resolves to it today.
            # Surfaces must-show, like rotation (spec §3) — never trimmed.
            cls = _Classification(goal.id in rotation_due_ids, _MUST_SHOW)
        else:
            cls = _classify(goal.id, chosen, plan_date, goals, plans)
        # A carried-over commitment always surfaces (presence tracking), even if
        # its recurrence would say "not due today" — dropping a sliding promise
        # is exactly the guilt dynamic we avoid.
        if not cls.due and not is_carry:
            # not eligible today and not carried → offer only via full_list
            continue
        item.bucket = cls.bucket
        is_need = chosen.level == Level.NEED
        # Carried items keep their NATURAL bucket (spec §3 bucket 3: carried =
        # candidates, i.e. trimmable). Carrying must never promote a want into
        # the protected tier — escalation-through-slippage is the report-card
        # dynamic in structural form ("yesterday's maybe hardens into today's
        # must"). A slid NEED stays protected because needs always are; chronic
        # slide is reassessment's job, not daily pressure's.
        if is_need or cls.bucket in (_MUST_SHOW, _FORCED):
            protected.append(item)
        else:
            trimmable.append(item)

        # 3b. Reassessment threshold. Accumulation is exempt entirely (§4.3).
        if chosen.recurrence_type == RecurrenceType.ACCUMULATION:
            continue
        if carry_count >= _REASSESS_THRESHOLD:
            gtype = _goal_type(chosen.recurrence_type)
            offers = _ONEOFF_OFFERS if gtype == "oneoff" else _RECURRING_OFFERS
            reassess_candidates.append(
                (
                    carry_count,
                    ReassessmentNudge(
                        goal_id=goal.id,
                        goal_title=goal.title,
                        goal_type=gtype,
                        offers=offers,
                    ),
                )
            )

    # 4. Smart subset (spec §3): protected always in; suggested trimmed to the
    #    cap. Heavy day (D-12) → a tighter cap. Needs are never trimmed.
    heavy = daily_signal is not None and is_heavy_day(
        daily_signal.whoop_recovery, daily_signal.sleep_hours
    )
    light = daily_signal is not None and is_light_day(
        daily_signal.whoop_recovery, daily_signal.sleep_hours
    )
    cap = _SUGGESTED_CAP_HEAVY if heavy else _SUGGESTED_CAP_NORMAL
    kept_suggested = trimmable[:cap]
    trimmed_out = trimmable[cap:]
    candidates = protected + kept_suggested

    # 5. Implementation-intention eligibility (D-3): flag at most one item — the
    #    carried-over candidate with the longest slide. "Hardest" stays the LLM's
    #    call (B5); this just surfaces the carried flag + a difficulty hint.
    _mark_if_then(candidates, goals)

    # 6. Lighter-day nudge (OQ-15): non-need items trimmed out of the subset are
    #    offered back. On a genuinely light day, everything non-need not already
    #    shown is fair game; otherwise just the ones the cap cut.
    nudge_offer = list(trimmed_out)
    if light:
        shown_ids = {c.goal_id for c in candidates}
        nudge_offer = [
            c
            for c in full_list
            if c.level != str(Level.NEED) and c.goal_id not in shown_ids
        ]

    # One nudge at a time — surface the most-chronic goal (highest count),
    # tie-broken by goal_id for determinism.
    reassessment = None
    if reassess_candidates:
        reassessment = max(reassess_candidates, key=lambda c: (c[0], -c[1].goal_id))[1]

    # 7. Group fan-out (behavior-spec §6) — shared goals as a SEPARATE block,
    #    never interleaved with the individual plan; plus neutral lowered-bar
    #    notices (D-16). No partner reference anywhere in here.
    group_block, shared_notices = _build_group_block(
        group_owner_ids or [], plan_date, goals
    )

    # 8. Chapter preamble — the person's authored seasonal framing (theme /
    #    focus / parked domains). Same trust level as Tier-1: human-written.
    active_chapter = goals.get_active_chapter(person_id, plan_date)

    return MorningContext(
        person_id=person_id,
        plan_date=plan_date,
        win_surface=win_surface,
        thin_day=thin_day,
        yesterday=yesterday_out,
        candidates=candidates,
        full_list=full_list,
        heavy_day=heavy,
        nudge_offer=nudge_offer,
        reassessment=reassessment,
        hypotheses=list(hypotheses or []),
        framing_excerpt=framing_excerpt,
        chapter_label=active_chapter.label if active_chapter else None,
        chapter_preamble=active_chapter.preamble if active_chapter else None,
        group_block=group_block,
        shared_notices=shared_notices,
        visualizations=list(visualizations or []),
    )


def _pick_current_version(versions: list[GoalVersion]) -> GoalVersion | None:
    """The version to pin: the current (effective_to IS NULL), active one,
    preferring the need level. Falls back to any active version if none is
    currently effective (defensive)."""
    current = [
        v
        for v in versions
        if v.lifecycle == VersionLifecycle.ACTIVE and v.effective_to is None
    ]
    pool = current or [v for v in versions if v.lifecycle == VersionLifecycle.ACTIVE]
    if not pool:
        return None
    return next((v for v in pool if v.level == Level.NEED), pool[0])


def _build_group_block(
    group_owner_ids: list[int],
    plan_date: date,
    goals: GoalRepositoryPort,
) -> tuple[list[CandidateItem], list[str]]:
    """Fan out each group's active goals into a separate block (need-pinned),
    plus a neutral notice for any shared goal whose bar was recently lowered
    (D-16). Deliberately partner-free: names no member, ranks no one."""
    block: list[CandidateItem] = []
    notices: list[str] = []
    for group_id in group_owner_ids:
        for goal in goals.get_full_goal_list(group_id, plan_date):
            detail = goals.get_goal_detail(goal.id)
            if not detail:
                continue
            _, versions = detail
            chosen = _pick_current_version(versions)
            if chosen is None:
                continue
            block.append(
                CandidateItem(
                    goal_id=goal.id,
                    goal_version_id=chosen.id,
                    goal_title=goal.title,
                    level=str(chosen.level),
                    recurrence_type=str(chosen.recurrence_type),
                    bucket="group",
                )
            )
            if _bar_was_lowered(chosen, versions):
                notices.append(
                    f"The shared goal '{goal.title}' had its bar adjusted "
                    "recently — worth a look together if either of you wants."
                )
    return block, notices


def _bar_was_lowered(current: GoalVersion, versions: list[GoalVersion]) -> bool:
    """True if the current need bar sits below an earlier need bar for the same
    goal (a re-anchor, B6). Comparison is numeric-target only; no person named."""
    if current.level != Level.NEED or current.target_quantity is None:
        return False
    prior_targets = [
        v.target_quantity
        for v in versions
        if v.level == Level.NEED
        and v.id != current.id
        and v.target_quantity is not None
    ]
    return any(current.target_quantity < pt for pt in prior_targets)


def _mark_if_then(candidates: list[CandidateItem], goals: GoalRepositoryPort) -> None:
    carried = [c for c in candidates if c.is_carry_over]
    if not carried:
        return
    # Pick the most-chronic carried item to flag — but the count is used only for
    # *selection* here; it never travels into the surfaced context. The hint is
    # deliberately qualitative (no number) so no miss count leaks past the
    # name-the-bar gate (OQ-COMP-1). "Hardest" is still the LLM's call.
    target = max(carried, key=lambda c: goals.get_carry_over_count(c.goal_id))
    target.if_then_eligible = True
    target.difficulty_hint = "has been carrying over"

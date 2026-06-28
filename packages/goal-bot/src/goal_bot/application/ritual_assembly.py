from datetime import date, timedelta

from goal_bot.application.morning_context import (
    CandidateItem,
    MorningContext,
    SurfacedWin,
    YesterdayItem,
)
from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.domain.entities import Level, PlanItemStatus, VersionLifecycle

_CANDIDATE_CAP = 5


def assemble_morning_context(
    person_id: int,
    plan_date: date,
    goals: GoalRepositoryPort,
    plans: PlanRepositoryPort,
    wins: WinRepositoryPort,
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

            yesterday_out.append(YesterdayItem(
                goal_title=title,
                status=item.status,
                what_shifted=item.what_shifted,
            ))

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

    # 3. Today's eligible goals → CandidateItems
    today_goals = goals.get_full_goal_list(person_id, plan_date)
    full_list: list[CandidateItem] = []

    for goal in today_goals:
        detail = goals.get_goal_detail(goal.id)
        if not detail:
            continue
        _, versions = detail
        active = [v for v in versions if v.lifecycle == VersionLifecycle.ACTIVE]
        if not active:
            continue
        need_v = next((v for v in active if v.level == Level.NEED), None)
        chosen = need_v or active[0]
        full_list.append(CandidateItem(
            goal_id=goal.id,
            goal_version_id=chosen.id,
            goal_title=goal.title,
            level=str(chosen.level),
            is_carry_over=goal.id in carry_over_ids,
        ))

    # 4. Candidates: need-level + carry-overs, capped
    # PHASE-B: replace with 3-bucket heuristic (heavy-day trim, lighter-day nudge)
    prioritized = [
        c for c in full_list
        if c.level == Level.NEED or c.is_carry_over
    ]
    candidates = prioritized[:_CANDIDATE_CAP]

    return MorningContext(
        person_id=person_id,
        plan_date=plan_date,
        win_surface=win_surface,
        thin_day=thin_day,
        yesterday=yesterday_out,
        candidates=candidates,
        full_list=full_list,
    )

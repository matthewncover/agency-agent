from dataclasses import dataclass
from datetime import date, timedelta

from agency_profile.application.ports import ProfileRepositoryPort
from task_tracker.application.query_client import DailySignal, TaskQueryClient

from goal_bot.application.morning_context import CandidateItem, InsightHypothesis
from goal_bot.application.morning_turn import MorningTurn, Session
from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.domain.entities import DailyPlanItem, PlanItemStatus

# Tier-1 framing excerpt cap — a runaway guard, not a target. Curation is the
# real limit (the doc should stay small enough to maintain by hand); the cap
# only stops an accidentally huge doc from flooding the prompt. Signal beats
# an arbitrary cutoff — raised from 1500 after the first real distillation
# pass showed the squeeze was cutting substance (2026-07-19).
_FRAMING_EXCERPT_MAX = 4000


@dataclass
class MorningService:
    goals: GoalRepositoryPort
    plans: PlanRepositoryPort
    wins: WinRepositoryPort
    turn: MorningTurn
    # Published task-tracker client (B1) — supplies the heavy-day daily signal
    # (D-12). Optional so the ritual runs even if task-tracker isn't wired.
    tasks: TaskQueryClient | None = None
    # Profile port (Tier-1 profile_doc) — feeds the framing-at-the-margin excerpt
    # (B5, §7a). Optional; framing is a light touch, never load-bearing.
    profiles: ProfileRepositoryPort | None = None

    def fire_morning(self, person_id: int, plan_date: date) -> Session:
        ctx = assemble_morning_context(
            person_id,
            plan_date,
            self.goals,
            self.plans,
            self.wins,
            daily_signal=self._daily_signal(person_id, plan_date),
            hypotheses=self._hypotheses(person_id),
            framing_excerpt=self._framing_excerpt(person_id),
            group_owner_ids=self._group_owner_ids(person_id),
        )
        # Persist both the individual plan and the fanned-out group items so a
        # shared goal is a real plan item in each member's plan (shared
        # completion targets it — behavior-spec §6).
        self._persist_provisional(
            person_id, plan_date, ctx.candidates + ctx.group_block
        )
        self._mark_yesterday_carried_over(person_id, plan_date)
        return self.turn.start(ctx)

    def handle_reply(self, session: Session, user_text: str) -> Session:
        return self.turn.reply(session, user_text)

    def _daily_signal(self, person_id: int, plan_date: date) -> DailySignal | None:
        # person_id (goalbot) == owner_id (task-tracker): same profile.person.
        if self.tasks is None:
            return None
        return self.tasks.get_daily_signal(person_id, plan_date)

    def _hypotheses(self, person_id: int) -> list[InsightHypothesis]:
        # Tier-3 patterns surfaced as confirm/reject hypotheses (D-11), never
        # verdicts. The digest itself carries no count and no partner reference.
        return [
            InsightHypothesis(
                insight_id=ins.id,
                text=ins.content,
                basis=ins.derived_from,
            )
            for ins in self.goals.list_active_insights(person_id)
            if ins.id is not None
        ]

    def _framing_excerpt(self, person_id: int) -> str | None:
        if self.profiles is None:
            return None
        doc = self.profiles.get_profile_doc(person_id)
        if doc is None or not doc.content:
            return None
        return doc.content[:_FRAMING_EXCERPT_MAX]

    def _group_owner_ids(self, person_id: int) -> list[int]:
        # Groups this person belongs to → their shared goals fan out (B7).
        if self.profiles is None:
            return []
        return self.profiles.list_groups_for_person(person_id)

    def _persist_provisional(
        self, person_id: int, plan_date: date, candidates: list[CandidateItem]
    ) -> None:
        plan = self.plans.get_or_create_plan(person_id, plan_date)
        existing = self.plans.get_plan_items(plan.id)
        existing_version_ids = {i.goal_version_id for i in existing}
        for c in candidates:
            if c.goal_version_id not in existing_version_ids:
                self.plans.add_plan_item(
                    DailyPlanItem(
                        daily_plan_id=plan.id,
                        goal_id=c.goal_id,
                        goal_version_id=c.goal_version_id,
                    )
                )

    def _mark_yesterday_carried_over(self, person_id: int, plan_date: date) -> None:
        """Mark yesterday's still-unresolved items as `carried_over` — presence
        tracking only. A `planned` (silent) item rolling forward is NOT a miss
        and advances no counter (that already happened, or didn't, at log time).
        `done`/`partial` items are left untouched (they resolved)."""
        prior = self.plans.get_plan_for_date(person_id, plan_date - timedelta(days=1))
        if not prior:
            return
        _, items = prior
        rolled = [
            i.id
            for i in items
            if i.status in {PlanItemStatus.PLANNED, PlanItemStatus.NOT_DONE}
        ]
        self.plans.mark_carried_over(rolled)

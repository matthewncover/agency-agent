from dataclasses import dataclass
from datetime import date

from goal_bot.application.morning_context import CandidateItem
from goal_bot.application.morning_turn import MorningTurn, Session
from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.domain.entities import DailyPlanItem


@dataclass
class MorningService:
    goals: GoalRepositoryPort
    plans: PlanRepositoryPort
    wins: WinRepositoryPort
    turn: MorningTurn

    def fire_morning(self, person_id: int, plan_date: date) -> Session:
        ctx = assemble_morning_context(
            person_id, plan_date, self.goals, self.plans, self.wins
        )
        self._persist_provisional(person_id, plan_date, ctx.candidates)
        return self.turn.start(ctx)

    def handle_reply(self, session: Session, user_text: str) -> Session:
        return self.turn.reply(session, user_text)

    def _persist_provisional(
        self, person_id: int, plan_date: date, candidates: list[CandidateItem]
    ) -> None:
        plan = self.plans.get_or_create_plan(person_id, plan_date)
        existing = self.plans.get_plan_items(plan.id)
        existing_version_ids = {i.goal_version_id for i in existing}
        for c in candidates:
            if c.goal_version_id not in existing_version_ids:
                self.plans.add_plan_item(DailyPlanItem(
                    daily_plan_id=plan.id,
                    goal_id=c.goal_id,
                    goal_version_id=c.goal_version_id,
                ))

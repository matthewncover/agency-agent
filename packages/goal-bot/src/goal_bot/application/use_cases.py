from dataclasses import dataclass
from datetime import date

from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.domain.entities import (
    Chapter,
    Goal,
    GoalVersion,
    PlanItemStatus,
    WinLogEntry,
)

_GOAL_IDENTITY_FIELDS = {"title", "tags", "chapter_id", "archived_at"}


@dataclass
class GoalUseCases:
    goals: GoalRepositoryPort
    plans: PlanRepositoryPort
    wins: WinRepositoryPort

    # --- authoring ---

    def create_chapter(
        self, owner: int, start: date, end: date, label: str | None
    ) -> int:
        return self.goals.create_chapter(
            Chapter(owner_profile_id=owner, start_date=start, end_date=end, label=label)
        ).id

    def create_goal(self, owner: int, title: str, chapter_id: int | None) -> int:
        return self.goals.create_goal(
            Goal(owner_profile_id=owner, title=title, chapter_id=chapter_id)
        ).id

    def create_goal_version(self, **kw) -> int:
        return self.goals.create_goal_version(GoalVersion(**kw)).id

    def update_goal(self, goal_id: int, fields: dict) -> dict:
        bad = set(fields) - _GOAL_IDENTITY_FIELDS
        if bad:
            raise ValueError(f"update_goal cannot set content fields: {sorted(bad)}")
        g = self.goals.update_goal(goal_id, fields)
        return g.model_dump()

    # --- ritual writes ---

    def log_outcome(
        self,
        daily_plan_item_id: int,
        status: str,
        quantity_actual: float | None = None,
    ) -> dict:
        st = PlanItemStatus(status)
        _allowed = {PlanItemStatus.DONE, PlanItemStatus.PARTIAL,
                    PlanItemStatus.NOT_DONE}
        if st not in _allowed:
            raise ValueError("log_outcome accepts only done|partial|not_done")
        item = self.plans.set_item_outcome(daily_plan_item_id, st, quantity_actual)
        return item.model_dump()

    def lock_in_plan(self, daily_plan_id: int, explicit: bool = True) -> dict:
        return self.plans.lock_in(daily_plan_id, explicit).model_dump()

    def add_win(self, owner: int, text: str, goal_id: int | None = None) -> dict:
        return self.wins.add_win(
            WinLogEntry(person_id=owner, text=text, source="manual", goal_id=goal_id)
        ).model_dump()

    def record_reflection(self, daily_plan_item_id: int, what_shifted: str) -> dict:
        self.plans.set_item_reflection(daily_plan_item_id, what_shifted)
        return {"ok": True}

    # --- reads ---

    def get_full_goal_list(self, owner: int, on: date) -> list[dict]:
        return [g.model_dump() for g in self.goals.get_full_goal_list(owner, on)]

    def get_plan(self, owner: int, on: date) -> dict:
        plan = self.plans.get_or_create_plan(owner, on)
        items = self.plans.get_plan_items(plan.id)
        return {"plan": plan.model_dump(), "items": [i.model_dump() for i in items]}

    def get_goal_detail(self, goal_id: int) -> dict:
        result = self.goals.get_goal_detail(goal_id)
        if result is None:
            return {}
        goal, versions = result
        return {
            "goal": goal.model_dump(),
            "versions": [v.model_dump() for v in versions],
        }

    def get_active_chapter(self, owner: int, on: date) -> dict | None:
        ch = self.goals.get_active_chapter(owner, on)
        return ch.model_dump() if ch else None

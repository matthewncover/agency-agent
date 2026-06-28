from abc import ABC, abstractmethod
from datetime import date

from goal_bot.domain.entities import (
    Chapter,
    DailyPlan,
    DailyPlanItem,
    Goal,
    GoalVersion,
    PlanItemStatus,
    WinLogEntry,
)


class GoalRepositoryPort(ABC):
    @abstractmethod
    def create_chapter(self, chapter: Chapter) -> Chapter: ...

    @abstractmethod
    def get_active_chapter(
        self, owner_profile_id: int, on: date
    ) -> Chapter | None: ...

    @abstractmethod
    def create_goal(self, goal: Goal) -> Goal: ...

    @abstractmethod
    def create_goal_version(self, version: GoalVersion) -> GoalVersion: ...

    @abstractmethod
    def get_goal_detail(
        self, goal_id: int
    ) -> tuple[Goal, list[GoalVersion]] | None: ...

    @abstractmethod
    def get_full_goal_list(
        self, owner_profile_id: int, on: date
    ) -> list[Goal]: ...

    @abstractmethod
    def update_goal(self, goal_id: int, fields: dict) -> Goal | None: ...


class PlanRepositoryPort(ABC):
    @abstractmethod
    def get_or_create_plan(
        self, person_id: int, plan_date: date
    ) -> DailyPlan: ...

    @abstractmethod
    def get_plan_items(self, daily_plan_id: int) -> list[DailyPlanItem]: ...

    @abstractmethod
    def add_plan_item(self, item: DailyPlanItem) -> DailyPlanItem: ...

    @abstractmethod
    def set_item_outcome(
        self,
        item_id: int,
        status: PlanItemStatus,
        quantity_actual: float | None = None,
    ) -> DailyPlanItem: ...

    @abstractmethod
    def set_item_reflection(self, item_id: int, what_shifted: str) -> None: ...

    @abstractmethod
    def lock_in(self, daily_plan_id: int, explicit: bool) -> DailyPlan: ...

    @abstractmethod
    def get_plan_for_date(
        self, person_id: int, plan_date: date
    ) -> tuple[DailyPlan, list[DailyPlanItem]] | None: ...


class WinRepositoryPort(ABC):
    @abstractmethod
    def add_win(self, win: WinLogEntry) -> WinLogEntry: ...

    @abstractmethod
    def list_wins(self, person_id: int, limit: int = 20) -> list[WinLogEntry]: ...

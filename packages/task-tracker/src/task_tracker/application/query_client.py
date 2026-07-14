"""Published, typed, read-only client contract for cross-package consumers.

goal-bot reaches task-tracker's data ONLY through this port — never MCP
transport, never raw cross-schema SQL (ADR-0007). Read-only for MVP; any future
write (e.g. completion sync) is a separate, explicit port + ADR.
"""

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel

from task_tracker.domain.entities import PersonalTaskEntity


class TaskStatus(BaseModel):
    """Status of a referenced task, for one-off goals' `task_ref` (ADR-0005)."""

    id: int
    source: str  # 'personal' | 'work'
    title: str
    status: str
    is_deleted: bool


class DailySignal(BaseModel):
    """The `daily_logs` Whoop/sleep signal the heavy-day trim uses (B4)."""

    date: date
    whoop_recovery: int | None = None
    whoop_hrv: int | None = None
    sleep_hours: float | None = None
    whoop_rhr: int | None = None


class TaskQueryClient(ABC):
    @abstractmethod
    def get_personal_candidates(
        self, owner_id: int, tiers: tuple[int, ...] = (2, 3)
    ) -> list[PersonalTaskEntity]:
        """Open, non-deleted, non-private personal tasks in the given tiers,
        for goal-setting candidate-gathering. `work_tasks` are never candidates
        (no work goals, ADR-0005); private tasks are never candidates
        (ADR-0018)."""

    @abstractmethod
    def get_task_status(
        self, source: str, task_id: int, owner_id: int
    ) -> TaskStatus | None:
        """Status of one referenced task (`source` ∈ {'personal','work'}) owned
        by `owner_id`, or None if it doesn't exist / isn't theirs / is private
        (ADR-0018 — private is deliberately indistinguishable from missing).

        None is a NO-SIGNAL answer: callers must treat it as "say nothing",
        never as evidence the task was completed, dropped, or removed. A live
        goal's ref can legitimately return None if its task was later marked
        private."""

    @abstractmethod
    def get_daily_signal(self, owner_id: int, day: date) -> DailySignal | None:
        """The Whoop/sleep signal for `(owner_id, day)`, or None if unlogged."""

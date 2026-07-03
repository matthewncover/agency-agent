from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel


class Level(StrEnum):
    NEED = "need"
    WANT = "want"


class RecurrenceType(StrEnum):
    ONEOFF = "oneoff"
    DAILY = "daily"
    ROTATION = "rotation"
    QUOTA = "quota"
    INTERVAL = "interval"
    FIXED_SCHEDULE = "fixed_schedule"
    ACCUMULATION = "accumulation"


class CompletionType(StrEnum):
    BINARY = "binary"
    QUANTITY = "quantity"
    DURATION = "duration"


class VersionLifecycle(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PlanItemStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    PARTIAL = "partial"
    NOT_DONE = "not_done"
    CARRIED_OVER = "carried_over"


class TaskRefSource(StrEnum):
    PERSONAL = "personal"
    WORK = "work"


class Chapter(BaseModel):
    id: int | None = None
    owner_profile_id: int
    label: str | None = None
    start_date: date
    end_date: date


class Goal(BaseModel):
    id: int | None = None
    owner_profile_id: int
    chapter_id: int | None = None
    title: str
    created_at: datetime | None = None
    archived_at: datetime | None = None


class GoalVersion(BaseModel):
    id: int | None = None
    goal_id: int | None = None  # assigned after the goal exists (batch create)
    version_no: int | None = None  # server-assigned per (goal_id, level) when None
    level: Level
    definition: str
    why: str | None = None
    recurrence_type: RecurrenceType
    recurrence_config: dict
    completion_type: CompletionType
    target_quantity: float | None = None
    quantity_unit: str | None = None
    task_ref_source: TaskRefSource | None = None
    task_ref_id: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    lifecycle: VersionLifecycle = VersionLifecycle.ACTIVE
    obstacles: list[str] = []  # verbatim anticipated-obstacle rows (template §4)


class DailyPlan(BaseModel):
    id: int | None = None
    person_id: int
    plan_date: date
    locked_in_at: datetime | None = None
    lock_was_explicit: bool = False


class DailyPlanItem(BaseModel):
    id: int | None = None
    daily_plan_id: int
    goal_id: int
    goal_version_id: int
    status: PlanItemStatus = PlanItemStatus.PLANNED
    quantity_actual: float | None = None
    what_shifted: str | None = None


class GoalState(BaseModel):
    """Mutable per-goal runtime state (goalbot.goal_state). The pointer fields
    drive interval/rotation surfacing; carry_over_count drives reassessment."""

    goal_id: int
    rotation_index: int | None = None
    last_completed_at: datetime | None = None
    carry_over_count: int = 0


class WinLogEntry(BaseModel):
    id: int | None = None
    person_id: int
    goal_id: int | None = None
    source: str
    text: str
    created_at: datetime | None = None


class Insight(BaseModel):
    """A Tier-3 advisory digest entry (goalbot.insight). Surfaced to the morning
    turn as a *hypothesis* the user confirms or rejects (D-11), never a verdict.
    Graduates into the Tier-1 profile only on human approval (non-negotiable 9)."""

    id: int | None = None
    person_id: int
    content: str
    status: str = "active"  # active | proposed_for_profile | graduated | dismissed
    derived_from: dict | None = None

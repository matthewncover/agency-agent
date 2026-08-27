from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PersonalTaskStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING = "waiting"
    DONE = "done"
    NUKED = "nuked"


class PersonalTaskEntity(BaseModel):
    id: int | None = None
    title: str
    tier: int | None = None
    status: PersonalTaskStatus = PersonalTaskStatus.NOT_STARTED
    blocked_reason: str | None = None
    deadline: date | None = None
    parent_task_id: int | None = None
    is_commitment: bool = False
    commitment_notes: str | None = None
    priority_rank: int | None = None
    pinned: bool = False
    private: bool = False
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    deleted_at: datetime | None = None

    # Computed fields (not stored)
    days_carried: int | None = None
    children: list["PersonalTaskEntity"] = Field(default_factory=list)
    is_stale: bool | None = None
    is_blocked: bool | None = None
    has_upcoming_deadline: bool | None = None


class DailyLogEntity(BaseModel):
    date: date
    whoop_recovery: int | None = None
    whoop_hrv: int | None = None
    whoop_sleep_hours: float | None = None
    whoop_rhr: int | None = None
    reflection_moved_forward: str | None = None
    reflection_didnt_move: str | None = None
    reflection_do_differently: str | None = None
    reflection_protect_tomorrow: str | None = None
    observations: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SystemMetaEntity(BaseModel):
    key: str
    value: str
    updated_at: datetime | None = None

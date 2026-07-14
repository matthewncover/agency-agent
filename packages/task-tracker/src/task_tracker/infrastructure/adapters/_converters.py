import sqlite3
from datetime import date, datetime

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    SprintEntity,
    TimeEntryEntity,
    WorkTaskEntity,
)


def row_to_work_task(row: sqlite3.Row) -> WorkTaskEntity:
    d = dict(row)
    d["is_commitment"] = bool(d.get("is_commitment", 0))
    for field in ("created_at", "updated_at", "completed_at", "deleted_at"):
        if d.get(field) and isinstance(d[field], str):
            d[field] = datetime.fromisoformat(d[field])
    if d.get("deadline") and isinstance(d["deadline"], str):
        d["deadline"] = date.fromisoformat(d["deadline"])
    if d.get("created_at") and d["status"] not in ("done", "nuked"):
        delta = datetime.now() - d["created_at"]
        d["days_carried"] = delta.days
    else:
        d["days_carried"] = None
    d.pop("actual_hours", None)
    d.pop("children", None)
    return WorkTaskEntity(**d)


def row_to_personal_task(row: sqlite3.Row) -> PersonalTaskEntity:
    d = dict(row)
    d["is_commitment"] = bool(d.get("is_commitment", 0))
    d["pinned"] = bool(d.get("pinned", 0))
    d["private"] = bool(d.get("private", 0))
    for field in ("created_at", "updated_at", "completed_at", "deleted_at"):
        if d.get(field) and isinstance(d[field], str):
            d[field] = datetime.fromisoformat(d[field])
    if d.get("deadline") and isinstance(d["deadline"], str):
        d["deadline"] = date.fromisoformat(d["deadline"])
    if d.get("created_at") and d["status"] not in ("done", "nuked"):
        delta = datetime.now() - d["created_at"]
        d["days_carried"] = delta.days
    else:
        d["days_carried"] = None
    d.pop("children", None)
    return PersonalTaskEntity(**d)


def row_to_time_entry(row: sqlite3.Row) -> TimeEntryEntity:
    d = dict(row)
    if d.get("date") and isinstance(d["date"], str):
        d["date"] = date.fromisoformat(d["date"])
    if d.get("created_at") and isinstance(d["created_at"], str):
        d["created_at"] = datetime.fromisoformat(d["created_at"])
    return TimeEntryEntity(**d)


def row_to_sprint(row: sqlite3.Row) -> SprintEntity:
    d = dict(row)
    if isinstance(d.get("start_date"), str):
        d["start_date"] = date.fromisoformat(d["start_date"])
    if isinstance(d.get("end_date"), str):
        d["end_date"] = date.fromisoformat(d["end_date"])
    return SprintEntity(**d)


def row_to_daily_log(row: sqlite3.Row) -> DailyLogEntity:
    d = dict(row)
    if isinstance(d.get("date"), str):
        d["date"] = date.fromisoformat(d["date"])
    for field in ("created_at", "updated_at"):
        if d.get(field) and isinstance(d[field], str):
            d[field] = datetime.fromisoformat(d[field])
    return DailyLogEntity(**d)

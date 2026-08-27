import sqlite3
from datetime import date, datetime

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
)


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


def row_to_daily_log(row: sqlite3.Row) -> DailyLogEntity:
    d = dict(row)
    if isinstance(d.get("date"), str):
        d["date"] = date.fromisoformat(d["date"])
    for field in ("created_at", "updated_at"):
        if d.get(field) and isinstance(d[field], str):
            d[field] = datetime.fromisoformat(d[field])
    return DailyLogEntity(**d)

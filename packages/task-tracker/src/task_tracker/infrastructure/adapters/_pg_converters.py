"""Row → entity converters for the Postgres adapters.

Postgres/SQLAlchemy hands back already-typed values (native date/datetime/
bool/float), so unlike the SQLite converters these do no string parsing. They
just drop the storage-only `owner_id` column (entities are person-agnostic —
ownership is carried by the adapter/client, per ADR-0004/0007) and compute the
same non-stored `days_carried` field.
"""

from datetime import datetime

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    SprintEntity,
    SystemMetaEntity,
    TimeEntryEntity,
    WorkTaskEntity,
)

_DONE_STATES = ("done", "nuked")
# Postgres hands back tz-aware timestamptz values; the SQLite schema stored
# naive localtime. The domain/use-case layers stay untouched (ADR-0009) and do
# naive arithmetic (`datetime.now() - created_at`), so the adapter boundary
# normalizes every timestamp to naive local wall-clock to keep them compatible.
_TS_FIELDS = ("created_at", "updated_at", "completed_at", "deleted_at")


def _naive_local(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _prep(row) -> dict:
    d = dict(row._mapping)
    d.pop("owner_id", None)
    for f in _TS_FIELDS:
        if f in d:
            d[f] = _naive_local(d[f])
    return d


def _days_carried(created_at: datetime | None, status: str) -> int | None:
    if created_at is None or status in _DONE_STATES:
        return None
    return (datetime.now() - created_at).days


def row_to_work_task(row) -> WorkTaskEntity:
    d = _prep(row)
    d["days_carried"] = _days_carried(d.get("created_at"), d["status"])
    return WorkTaskEntity(**d)


def row_to_personal_task(row) -> PersonalTaskEntity:
    d = _prep(row)
    d["days_carried"] = _days_carried(d.get("created_at"), d["status"])
    return PersonalTaskEntity(**d)


def row_to_time_entry(row) -> TimeEntryEntity:
    return TimeEntryEntity(**_prep(row))


def row_to_sprint(row) -> SprintEntity:
    return SprintEntity(**dict(row._mapping))


def row_to_daily_log(row) -> DailyLogEntity:
    return DailyLogEntity(**_prep(row))


def row_to_system_meta(row) -> SystemMetaEntity:
    return SystemMetaEntity(**_prep(row))

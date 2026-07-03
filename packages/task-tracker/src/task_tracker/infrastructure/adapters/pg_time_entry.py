from datetime import date, timedelta

from sqlalchemy import Engine, delete, func, insert, select

from task_tracker.application.ports import TimeEntryRepositoryPort
from task_tracker.domain.entities import TimeEntryEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_time_entry


class PgTimeEntryRepositoryAdapter(TimeEntryRepositoryPort):
    """Time entries derive ownership through their work_task, so this adapter is
    person-agnostic (no owner_id column of its own)."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self, entry: TimeEntryEntity) -> TimeEntryEntity:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.time_entries)
                .values(
                    work_task_id=entry.work_task_id,
                    date=entry.date,
                    duration_minutes=entry.duration_minutes,
                    jn_bucket=_enum_val(entry.jn_bucket),
                    notes=entry.notes,
                )
                .returning(t.time_entries)
            ).one()
        return row_to_time_entry(row)

    def get_for_task(self, work_task_id: int) -> list[TimeEntryEntity]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.time_entries)
                .where(t.time_entries.c.work_task_id == work_task_id)
                .order_by(t.time_entries.c.date)
            ).all()
        return [row_to_time_entry(r) for r in rows]

    def get_timecard(self, start_date: date, end_date: date) -> list[dict]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(
                    t.time_entries.c.date,
                    t.time_entries.c.jn_bucket,
                    func.sum(t.time_entries.c.duration_minutes).label("total_minutes"),
                    func.array_agg(t.work_tasks.c.ods_ticket.distinct()).label(
                        "ods_tickets"
                    ),
                )
                .select_from(
                    t.time_entries.join(
                        t.work_tasks,
                        t.work_tasks.c.id == t.time_entries.c.work_task_id,
                    )
                )
                .where(t.time_entries.c.date >= start_date)
                .where(t.time_entries.c.date <= end_date)
                .group_by(t.time_entries.c.date, t.time_entries.c.jn_bucket)
                .order_by(t.time_entries.c.date, t.time_entries.c.jn_bucket)
            ).all()
        return [
            {
                "date": str(row.date),
                "jn_bucket": row.jn_bucket,
                "total_minutes": row.total_minutes,
                "total_hours": round(row.total_minutes / 60, 2),
                "ods_tickets": [x for x in (row.ods_tickets or []) if x],
            }
            for row in rows
        ]

    def get_time_gaps(self, start_date: date, end_date: date) -> list[dict]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(
                    t.time_entries.c.date,
                    func.sum(t.time_entries.c.duration_minutes).label("total_minutes"),
                )
                .where(t.time_entries.c.date >= start_date)
                .where(t.time_entries.c.date <= end_date)
                .group_by(t.time_entries.c.date)
                .order_by(t.time_entries.c.date)
            ).all()
        logged = {row.date: row.total_minutes for row in rows}
        expected_minutes = 8 * 60
        result = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                minutes = logged.get(current, 0)
                result.append(
                    {
                        "date": str(current),
                        "logged_minutes": minutes,
                        "logged_hours": round(minutes / 60, 2),
                        "expected_minutes": expected_minutes,
                        "gap_minutes": max(0, expected_minutes - minutes),
                        "gap_hours": round(max(0, expected_minutes - minutes) / 60, 2),
                    }
                )
            current += timedelta(days=1)
        return result

    def get_actual_hours(self, work_task_id: int) -> float:
        with self._engine.connect() as c:
            total = c.execute(
                select(
                    func.coalesce(func.sum(t.time_entries.c.duration_minutes), 0)
                ).where(t.time_entries.c.work_task_id == work_task_id)
            ).scalar_one()
        return round(total / 60, 2)

    def delete(self, time_entry_id: int) -> TimeEntryEntity | None:
        with self._engine.begin() as c:
            row = c.execute(
                delete(t.time_entries)
                .where(t.time_entries.c.id == time_entry_id)
                .returning(t.time_entries)
            ).one_or_none()
        return row_to_time_entry(row) if row else None


def _enum_val(v):
    return v.value if hasattr(v, "value") else v

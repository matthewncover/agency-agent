import sqlite3
from collections.abc import Callable
from datetime import date, timedelta

from task_tracker.application.ports import TimeEntryRepositoryPort
from task_tracker.domain.entities import TimeEntryEntity
from task_tracker.infrastructure.adapters._converters import (
    row_to_time_entry,
)


class SqliteTimeEntryRepositoryAdapter(TimeEntryRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def create(self, entry: TimeEntryEntity) -> TimeEntryEntity:
        conn = self._conn_factory()
        cur = conn.execute(
            """INSERT INTO time_entries
            (work_task_id, date, duration_minutes, jn_bucket, notes)
            VALUES (?, ?, ?, ?, ?)""",
            (
                entry.work_task_id,
                str(entry.date),
                entry.duration_minutes,
                entry.jn_bucket,
                entry.notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM time_entries WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return row_to_time_entry(row)

    def get_for_task(self, work_task_id: int) -> list[TimeEntryEntity]:
        conn = self._conn_factory()
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE work_task_id = ? ORDER BY date",
            (work_task_id,),
        ).fetchall()
        return [row_to_time_entry(r) for r in rows]

    def get_timecard(self, start_date: date, end_date: date) -> list[dict]:
        conn = self._conn_factory()
        rows = conn.execute(
            """SELECT
                te.date,
                te.jn_bucket,
                SUM(te.duration_minutes) as total_minutes,
                GROUP_CONCAT(DISTINCT wt.ods_ticket) as ods_tickets
            FROM time_entries te
            JOIN work_tasks wt ON wt.id = te.work_task_id
            WHERE te.date >= ? AND te.date <= ?
            GROUP BY te.date, te.jn_bucket
            ORDER BY te.date, te.jn_bucket""",
            (str(start_date), str(end_date)),
        ).fetchall()
        return [
            {
                "date": row["date"],
                "jn_bucket": row["jn_bucket"],
                "total_minutes": row["total_minutes"],
                "total_hours": round(row["total_minutes"] / 60, 2),
                "ods_tickets": (
                    row["ods_tickets"].split(",") if row["ods_tickets"] else []
                ),
            }
            for row in rows
        ]

    def get_time_gaps(self, start_date: date, end_date: date) -> list[dict]:
        conn = self._conn_factory()
        rows = conn.execute(
            """SELECT date, SUM(duration_minutes) as total_minutes
            FROM time_entries
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date""",
            (str(start_date), str(end_date)),
        ).fetchall()
        logged = {row["date"]: row["total_minutes"] for row in rows}
        expected_minutes = 8 * 60
        result = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                date_str = str(current)
                minutes = logged.get(date_str, 0)
                result.append(
                    {
                        "date": date_str,
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
        conn = self._conn_factory()
        row = conn.execute(
            """SELECT COALESCE(SUM(duration_minutes), 0) as total
            FROM time_entries WHERE work_task_id = ?""",
            (work_task_id,),
        ).fetchone()
        return round(row["total"] / 60, 2)

    def delete(self, time_entry_id: int) -> TimeEntryEntity | None:
        conn = self._conn_factory()
        row = conn.execute(
            "SELECT * FROM time_entries WHERE id = ?",
            (time_entry_id,),
        ).fetchone()
        if row is None:
            return None
        entry = row_to_time_entry(row)
        conn.execute("DELETE FROM time_entries WHERE id = ?", (time_entry_id,))
        conn.commit()
        return entry

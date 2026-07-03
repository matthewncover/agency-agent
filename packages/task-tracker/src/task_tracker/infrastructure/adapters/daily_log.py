import sqlite3
from collections.abc import Callable
from datetime import date

from task_tracker.application.ports import DailyLogRepositoryPort
from task_tracker.domain.entities import DailyLogEntity
from task_tracker.infrastructure.adapters._converters import (
    row_to_daily_log,
)


class SqliteDailyLogRepositoryAdapter(DailyLogRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def create_or_update(self, log: DailyLogEntity) -> DailyLogEntity:
        conn = self._conn_factory()
        conn.execute(
            """INSERT INTO daily_logs
            (date, whoop_recovery, whoop_hrv,
             whoop_sleep_hours, whoop_rhr, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                whoop_recovery = COALESCE(
                    excluded.whoop_recovery,
                    daily_logs.whoop_recovery
                ),
                whoop_hrv = COALESCE(
                    excluded.whoop_hrv,
                    daily_logs.whoop_hrv
                ),
                whoop_sleep_hours = COALESCE(
                    excluded.whoop_sleep_hours,
                    daily_logs.whoop_sleep_hours
                ),
                whoop_rhr = COALESCE(
                    excluded.whoop_rhr,
                    daily_logs.whoop_rhr
                ),
                notes = COALESCE(
                    excluded.notes,
                    daily_logs.notes
                )""",
            (
                str(log.date),
                log.whoop_recovery,
                log.whoop_hrv,
                log.whoop_sleep_hours,
                log.whoop_rhr,
                log.notes,
            ),
        )
        conn.commit()
        return self.get(log.date)

    def get(self, target_date: date) -> DailyLogEntity | None:
        conn = self._conn_factory()
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE date = ?",
            (str(target_date),),
        ).fetchone()
        return row_to_daily_log(row) if row else None

    def get_range(self, start_date: date, end_date: date) -> list[DailyLogEntity]:
        conn = self._conn_factory()
        rows = conn.execute(
            "SELECT * FROM daily_logs WHERE date >= ? AND date <= ? ORDER BY date",
            (str(start_date), str(end_date)),
        ).fetchall()
        return [row_to_daily_log(r) for r in rows]

    def update_reflection(
        self, target_date: date, fields: dict
    ) -> DailyLogEntity | None:
        conn = self._conn_factory()
        existing = self.get(target_date)
        if existing is None:
            conn.execute(
                "INSERT INTO daily_logs (date) VALUES (?)",
                (str(target_date),),
            )
            conn.commit()

        allowed = {
            "reflection_moved_forward",
            "reflection_didnt_move",
            "reflection_do_differently",
            "reflection_protect_tomorrow",
            "observations",
        }
        field_map = {
            "moved_forward": "reflection_moved_forward",
            "didnt_move": "reflection_didnt_move",
            "do_differently": "reflection_do_differently",
            "protect_tomorrow": "reflection_protect_tomorrow",
            "observations": "observations",
        }
        updates = {}
        for k, v in fields.items():
            col = field_map.get(k, k)
            if col in allowed and v is not None:
                updates[col] = v

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [str(target_date)]
            conn.execute(
                f"UPDATE daily_logs SET {set_clause} WHERE date = ?",
                values,
            )
            conn.commit()

        return self.get(target_date)

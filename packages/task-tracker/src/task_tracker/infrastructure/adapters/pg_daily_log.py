from datetime import date

from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from task_tracker.application.ports import DailyLogRepositoryPort
from task_tracker.domain.entities import DailyLogEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_daily_log

_REFLECTION_ALLOWED = {
    "reflection_moved_forward",
    "reflection_didnt_move",
    "reflection_do_differently",
    "reflection_protect_tomorrow",
    "observations",
}
_REFLECTION_FIELD_MAP = {
    "moved_forward": "reflection_moved_forward",
    "didnt_move": "reflection_didnt_move",
    "do_differently": "reflection_do_differently",
    "protect_tomorrow": "reflection_protect_tomorrow",
    "observations": "observations",
}


class PgDailyLogRepositoryAdapter(DailyLogRepositoryPort):
    """Daily Whoop/sleep + reflection log, keyed per (owner_id, date)."""

    def __init__(self, engine: Engine, owner_id: int):
        self._engine = engine
        self._owner_id = owner_id

    def create_or_update(self, log: DailyLogEntity) -> DailyLogEntity:
        cols = t.daily_logs.c
        stmt = pg_insert(t.daily_logs).values(
            owner_id=self._owner_id,
            date=log.date,
            whoop_recovery=log.whoop_recovery,
            whoop_hrv=log.whoop_hrv,
            whoop_sleep_hours=log.whoop_sleep_hours,
            whoop_rhr=log.whoop_rhr,
            notes=log.notes,
        )
        excl = stmt.excluded
        # COALESCE(new, existing): a null in the incoming log never wipes a
        # stored reading (matches the SQLite impl).
        stmt = stmt.on_conflict_do_update(
            index_elements=[cols.owner_id, cols.date],
            set_={
                "whoop_recovery": func.coalesce(
                    excl.whoop_recovery, cols.whoop_recovery
                ),
                "whoop_hrv": func.coalesce(excl.whoop_hrv, cols.whoop_hrv),
                "whoop_sleep_hours": func.coalesce(
                    excl.whoop_sleep_hours, cols.whoop_sleep_hours
                ),
                "whoop_rhr": func.coalesce(excl.whoop_rhr, cols.whoop_rhr),
                "notes": func.coalesce(excl.notes, cols.notes),
                "updated_at": func.now(),
            },
        )
        with self._engine.begin() as c:
            c.execute(stmt)
        return self.get(log.date)

    def get(self, target_date: date) -> DailyLogEntity | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.daily_logs)
                .where(t.daily_logs.c.owner_id == self._owner_id)
                .where(t.daily_logs.c.date == target_date)
            ).one_or_none()
        return row_to_daily_log(row) if row else None

    def get_range(self, start_date: date, end_date: date) -> list[DailyLogEntity]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.daily_logs)
                .where(t.daily_logs.c.owner_id == self._owner_id)
                .where(t.daily_logs.c.date >= start_date)
                .where(t.daily_logs.c.date <= end_date)
                .order_by(t.daily_logs.c.date)
            ).all()
        return [row_to_daily_log(r) for r in rows]

    def update_reflection(
        self, target_date: date, fields: dict
    ) -> DailyLogEntity | None:
        updates = {}
        for k, v in fields.items():
            col = _REFLECTION_FIELD_MAP.get(k, k)
            if col in _REFLECTION_ALLOWED and v is not None:
                updates[col] = v

        with self._engine.begin() as c:
            # Ensure the row exists (reflections can precede any Whoop reading).
            c.execute(
                pg_insert(t.daily_logs)
                .values(owner_id=self._owner_id, date=target_date)
                .on_conflict_do_nothing(
                    index_elements=[t.daily_logs.c.owner_id, t.daily_logs.c.date]
                )
            )
            if updates:
                c.execute(
                    update(t.daily_logs)
                    .where(t.daily_logs.c.owner_id == self._owner_id)
                    .where(t.daily_logs.c.date == target_date)
                    .values(**updates)
                )
        return self.get(target_date)

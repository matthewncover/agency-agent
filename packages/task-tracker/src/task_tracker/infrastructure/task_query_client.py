from datetime import date

from sqlalchemy import Engine, func, select

from task_tracker.application.query_client import (
    DailySignal,
    TaskQueryClient,
    TaskStatus,
)
from task_tracker.domain.entities import PersonalTaskEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_personal_task

_OPEN_STATES = ("done", "nuked")


class PgTaskQueryClient(TaskQueryClient):
    """Postgres implementation of the published read-only client (ADR-0007).

    Reads only task-tracker's own `tasktracker` schema; it never crosses into
    goalbot/profile tables. Constructed by goal-bot's composition root with the
    shared engine.
    """

    def __init__(self, engine: Engine):
        self._engine = engine

    def get_personal_candidates(
        self, owner_id: int, tiers: tuple[int, ...] = (2, 3)
    ) -> list[PersonalTaskEntity]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.personal_tasks)
                .where(t.personal_tasks.c.owner_id == owner_id)
                .where(t.personal_tasks.c.tier.in_(tiers))
                .where(t.personal_tasks.c.status.notin_(_OPEN_STATES))
                .where(t.personal_tasks.c.deleted_at.is_(None))
                .where(t.personal_tasks.c.private.is_(False))
                .order_by(
                    func.coalesce(t.personal_tasks.c.tier, 99),
                    func.coalesce(t.personal_tasks.c.priority_rank, 999999),
                    t.personal_tasks.c.id,
                )
            ).all()
        return [row_to_personal_task(r) for r in rows]

    def get_task_status(
        self, source: str, task_id: int, owner_id: int
    ) -> TaskStatus | None:
        if source != "personal":
            raise ValueError(f"Invalid task source: {source!r}")
        tbl = t.personal_tasks

        stmt = (
            select(tbl.c.id, tbl.c.title, tbl.c.status, tbl.c.deleted_at)
            .where(tbl.c.id == task_id)
            .where(tbl.c.owner_id == owner_id)
            # Private tasks are invisible to goal-bot (ADR-0018): the answer
            # is the same None as "doesn't exist", by design.
            .where(tbl.c.private.is_(False))
        )
        with self._engine.connect() as c:
            row = c.execute(stmt).one_or_none()
        if row is None:
            return None
        return TaskStatus(
            id=row.id,
            source=source,
            title=row.title,
            status=row.status,
            is_deleted=row.deleted_at is not None,
        )

    def get_daily_signal(self, owner_id: int, day: date) -> DailySignal | None:
        cols = t.daily_logs.c
        with self._engine.connect() as c:
            row = c.execute(
                select(
                    cols.date,
                    cols.whoop_recovery,
                    cols.whoop_hrv,
                    cols.whoop_sleep_hours,
                    cols.whoop_rhr,
                )
                .where(cols.owner_id == owner_id)
                .where(cols.date == day)
            ).one_or_none()
        if row is None:
            return None
        return DailySignal(
            date=row.date,
            whoop_recovery=row.whoop_recovery,
            whoop_hrv=row.whoop_hrv,
            sleep_hours=row.whoop_sleep_hours,
            whoop_rhr=row.whoop_rhr,
        )

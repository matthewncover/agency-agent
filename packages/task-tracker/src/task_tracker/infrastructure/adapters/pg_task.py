from datetime import date, datetime, time, timedelta

from sqlalchemy import (
    Connection,
    Engine,
    and_,
    case,
    func,
    insert,
    or_,
    select,
    update,
)

from task_tracker.application.ports import TaskRepositoryPort
from task_tracker.domain.entities import PersonalTaskEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_personal_task

_OPEN_STATES = ("done", "nuked")


class PgTaskRepositoryAdapter(TaskRepositoryPort):
    """Postgres task repository. `owner_id` stamps every write and scopes every
    read, so the person is a DB fact rather than an app assumption (ADR-0004).

    `include_private=False` builds the shared-surface variant (ADR-0018): every
    read adds `private = false`, so private tasks are invisible —
    indistinguishable from nonexistent — at the SQL layer, not by caller
    discipline."""

    def __init__(self, engine: Engine, owner_id: int, include_private: bool = True):
        self._engine = engine
        self._owner_id = owner_id
        self._include_private = include_private

    def _privacy(self) -> list:
        """Extra WHERE criteria hiding private tasks on the shared surface.
        Empty (a no-op in `.where()`) for the full-access adapter."""
        if not self._include_private:
            return [t.personal_tasks.c.private.is_(False)]
        return []

    def create_personal_task(self, task: PersonalTaskEntity) -> PersonalTaskEntity:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.personal_tasks)
                .values(
                    owner_id=self._owner_id,
                    title=task.title,
                    tier=task.tier,
                    status=_enum_val(task.status),
                    blocked_reason=task.blocked_reason,
                    deadline=task.deadline,
                    parent_task_id=task.parent_task_id,
                    is_commitment=task.is_commitment,
                    commitment_notes=task.commitment_notes,
                    priority_rank=task.priority_rank,
                    pinned=task.pinned,
                    private=task.private,
                    notes=task.notes,
                )
                .returning(t.personal_tasks)
            ).one()
            return self._load_personal_task(c, row.id)

    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        with self._engine.connect() as c:
            return self._load_personal_task(c, task_id)

    def update_personal_task(
        self, task_id: int, fields: dict
    ) -> PersonalTaskEntity | None:
        with self._engine.begin() as c:
            if fields:
                c.execute(
                    update(t.personal_tasks)
                    .where(t.personal_tasks.c.id == task_id)
                    .where(t.personal_tasks.c.owner_id == self._owner_id)
                    .where(t.personal_tasks.c.deleted_at.is_(None))
                    .values(**_clean(fields))
                )
            return self._load_personal_task(c, task_id)

    def soft_delete_personal_task(self, task_id: int) -> bool:
        with self._engine.begin() as c:
            res = c.execute(
                update(t.personal_tasks)
                .where(t.personal_tasks.c.id == task_id)
                .where(t.personal_tasks.c.owner_id == self._owner_id)
                .where(t.personal_tasks.c.deleted_at.is_(None))
                .values(deleted_at=func.now())
            )
            return res.rowcount > 0

    def restore_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        with self._engine.begin() as c:
            c.execute(
                update(t.personal_tasks)
                .where(t.personal_tasks.c.id == task_id)
                .where(t.personal_tasks.c.owner_id == self._owner_id)
                .where(t.personal_tasks.c.deleted_at.is_not(None))
                .values(deleted_at=None)
            )
            return self._load_personal_task(c, task_id)

    def search_tasks(
        self,
        query: str,
        include_done: bool = False,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        like = f"%{query}%"
        tbl = t.personal_tasks
        title_rank = case((tbl.c.title.ilike(like), 0), else_=1)
        conds = [
            tbl.c.owner_id == self._owner_id,
            or_(tbl.c.title.ilike(like), tbl.c.notes.ilike(like)),
            *self._privacy(),
        ]
        if not include_done:
            conds.append(tbl.c.status != "done")
        if not include_deleted:
            conds.append(tbl.c.deleted_at.is_(None))
        with self._engine.connect() as c:
            rows = c.execute(
                select(
                    tbl.c.id,
                    tbl.c.title,
                    tbl.c.tier,
                    tbl.c.status,
                    title_rank.label("title_rank"),
                )
                .where(and_(*conds))
                .order_by("title_rank", tbl.c.id)
                .limit(limit)
            ).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "tier": row.tier,
                "status": row.status,
            }
            for row in rows
        ]

    def get_open_personal_tasks(
        self, min_days_open: int | None = None
    ) -> list[PersonalTaskEntity]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.personal_tasks)
                .where(t.personal_tasks.c.owner_id == self._owner_id)
                .where(t.personal_tasks.c.status.notin_(_OPEN_STATES))
                .where(t.personal_tasks.c.deleted_at.is_(None))
                .where(t.personal_tasks.c.parent_task_id.is_(None))
                .where(*self._privacy())
                .order_by(
                    func.coalesce(t.personal_tasks.c.tier, 99),
                    func.coalesce(t.personal_tasks.c.priority_rank, 999999),
                )
            ).all()
            return self._assemble_open(c, rows, min_days_open)

    def get_tasks_updated_on(self, target_date: date) -> list[PersonalTaskEntity]:
        # "Updated on <date>" means the target's local calendar day. Build
        # tz-aware bounds (local midnight → next local midnight) so the compare
        # against timestamptz is correct regardless of the DB session timezone.
        start = datetime.combine(target_date, time.min).astimezone()
        end = datetime.combine(target_date + timedelta(days=1), time.min).astimezone()
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.personal_tasks)
                .where(t.personal_tasks.c.owner_id == self._owner_id)
                .where(t.personal_tasks.c.deleted_at.is_(None))
                .where(t.personal_tasks.c.updated_at >= start)
                .where(t.personal_tasks.c.updated_at < end)
                .where(*self._privacy())
            ).all()

        tasks = [row_to_personal_task(r) for r in rows]
        for task in tasks:
            task.notes = None
        return tasks

    # ---- internal helpers -------------------------------------------------

    def _load_personal_task(
        self, c: Connection, task_id: int
    ) -> PersonalTaskEntity | None:
        row = c.execute(
            select(t.personal_tasks)
            .where(t.personal_tasks.c.id == task_id)
            .where(t.personal_tasks.c.owner_id == self._owner_id)
            .where(t.personal_tasks.c.deleted_at.is_(None))
            .where(*self._privacy())
        ).one_or_none()
        if row is None:
            return None
        task = row_to_personal_task(row)
        child_rows = c.execute(
            select(t.personal_tasks)
            .where(t.personal_tasks.c.parent_task_id == task_id)
            .where(t.personal_tasks.c.deleted_at.is_(None))
            .where(*self._privacy())
        ).all()
        task.children = [row_to_personal_task(r) for r in child_rows]
        return task

    def _assemble_open(self, c, rows, min_days_open):
        tbl = t.personal_tasks
        tasks = []
        for row in rows:
            task = row_to_personal_task(row)
            task.notes = None
            child_rows = c.execute(
                select(tbl)
                .where(tbl.c.parent_task_id == task.id)
                .where(tbl.c.status.notin_(_OPEN_STATES))
                .where(tbl.c.deleted_at.is_(None))
                .where(*self._privacy())
                .order_by(func.coalesce(tbl.c.priority_rank, 999999))
            ).all()
            task.children = [row_to_personal_task(r) for r in child_rows]
            for child in task.children:
                child.notes = None
            if min_days_open is not None:
                if task.days_carried is None or task.days_carried < min_days_open:
                    continue
            tasks.append(task)
        return tasks


def _enum_val(v):
    """StrEnum → its str value for the DB (None passes through)."""
    return v.value if hasattr(v, "value") else v


def _clean(fields: dict) -> dict:
    """Coerce any StrEnum values in an update payload to plain strings."""
    return {k: _enum_val(v) for k, v in fields.items()}

from datetime import date, datetime, time, timedelta

from sqlalchemy import (
    Connection,
    Engine,
    and_,
    case,
    func,
    insert,
    null,
    or_,
    select,
    update,
)

from task_tracker.application.ports import TaskRepositoryPort
from task_tracker.domain.entities import PersonalTaskEntity, WorkTaskEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import (
    row_to_personal_task,
    row_to_work_task,
)

_OPEN_STATES = ("done", "nuked")
_WORK_COMMITMENT_ORDER = case(
    (t.work_tasks.c.commitment_level == "sprint_committed", 1),
    (t.work_tasks.c.commitment_level == "sprint_stretch", 2),
    (t.work_tasks.c.commitment_level == "backlog", 3),
    else_=4,
)


class PgTaskRepositoryAdapter(TaskRepositoryPort):
    """Postgres task repository. `owner_id` stamps every write and scopes every
    read, so the person is a DB fact rather than an app assumption (ADR-0004)."""

    def __init__(self, engine: Engine, owner_id: int):
        self._engine = engine
        self._owner_id = owner_id

    def create_work_task(self, task: WorkTaskEntity) -> WorkTaskEntity:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.work_tasks)
                .values(
                    owner_id=self._owner_id,
                    title=task.title,
                    ods_ticket=task.ods_ticket,
                    sprint_id=task.sprint_id,
                    commitment_level=_enum_val(task.commitment_level),
                    jn_bucket=_enum_val(task.jn_bucket),
                    status=_enum_val(task.status),
                    blocked_reason=task.blocked_reason,
                    estimate_hours=task.estimate_hours,
                    deadline=task.deadline,
                    parent_task_id=task.parent_task_id,
                    is_commitment=task.is_commitment,
                    commitment_notes=task.commitment_notes,
                    priority_rank=task.priority_rank,
                    notes=task.notes,
                )
                .returning(t.work_tasks)
            ).one()
            return self._load_work_task(c, row.id)

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
                    notes=task.notes,
                )
                .returning(t.personal_tasks)
            ).one()
            return self._load_personal_task(c, row.id)

    def get_work_task(self, task_id: int) -> WorkTaskEntity | None:
        with self._engine.connect() as c:
            return self._load_work_task(c, task_id)

    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        with self._engine.connect() as c:
            return self._load_personal_task(c, task_id)

    def update_work_task(self, task_id: int, fields: dict) -> WorkTaskEntity | None:
        with self._engine.begin() as c:
            if fields:
                c.execute(
                    update(t.work_tasks)
                    .where(t.work_tasks.c.id == task_id)
                    .where(t.work_tasks.c.owner_id == self._owner_id)
                    .where(t.work_tasks.c.deleted_at.is_(None))
                    .values(**_clean(fields))
                )
            return self._load_work_task(c, task_id)

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

    def soft_delete_work_task(self, task_id: int) -> bool:
        with self._engine.begin() as c:
            res = c.execute(
                update(t.work_tasks)
                .where(t.work_tasks.c.id == task_id)
                .where(t.work_tasks.c.owner_id == self._owner_id)
                .where(t.work_tasks.c.deleted_at.is_(None))
                .values(deleted_at=func.now())
            )
            return res.rowcount > 0

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

    def restore_work_task(self, task_id: int) -> WorkTaskEntity | None:
        with self._engine.begin() as c:
            c.execute(
                update(t.work_tasks)
                .where(t.work_tasks.c.id == task_id)
                .where(t.work_tasks.c.owner_id == self._owner_id)
                .where(t.work_tasks.c.deleted_at.is_not(None))
                .values(deleted_at=None)
            )
            return self._load_work_task(c, task_id)

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
        results: list[dict] = []
        specs = (
            ("work", t.work_tasks, null()),
            ("personal", t.personal_tasks, t.personal_tasks.c.tier),
        )
        with self._engine.connect() as c:
            for task_type, tbl, tier_expr in specs:
                title_rank = case((tbl.c.title.like(like), 0), else_=1)
                conds = [
                    tbl.c.owner_id == self._owner_id,
                    or_(tbl.c.title.like(like), tbl.c.notes.like(like)),
                ]
                if not include_done:
                    conds.append(tbl.c.status != "done")
                if not include_deleted:
                    conds.append(tbl.c.deleted_at.is_(None))
                rows = c.execute(
                    select(
                        tbl.c.id,
                        tbl.c.title,
                        tier_expr.label("tier"),
                        tbl.c.status,
                        title_rank.label("title_rank"),
                    )
                    .where(and_(*conds))
                    .order_by("title_rank", tbl.c.id)
                ).all()
                for row in rows:
                    results.append(
                        {
                            "id": row.id,
                            "title": row.title,
                            "tier": row.tier,
                            "status": row.status,
                            "type": task_type,
                            "_title_rank": row.title_rank,
                        }
                    )
        results.sort(key=lambda r: (r.pop("_title_rank"), r["type"], r["id"]))
        return results[:limit]

    def get_estimation_data(
        self, n: int | None = None, task_type: str | None = None
    ) -> list[dict]:
        # Only work tasks carry estimate_hours + time entries (see SQLite impl).
        if task_type == "personal":
            return []
        actual_minutes = (
            select(func.coalesce(func.sum(t.time_entries.c.duration_minutes), 0))
            .where(t.time_entries.c.work_task_id == t.work_tasks.c.id)
            .scalar_subquery()
        )
        stmt = (
            select(
                t.work_tasks.c.id,
                t.work_tasks.c.title,
                t.work_tasks.c.estimate_hours,
                actual_minutes.label("actual_minutes"),
            )
            .where(t.work_tasks.c.owner_id == self._owner_id)
            .where(t.work_tasks.c.status == "done")
            .where(t.work_tasks.c.deleted_at.is_(None))
            .where(t.work_tasks.c.estimate_hours.is_not(None))
            .order_by(t.work_tasks.c.completed_at.desc(), t.work_tasks.c.id.desc())
        )
        if n is not None:
            stmt = stmt.limit(n)
        with self._engine.connect() as c:
            rows = c.execute(stmt).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "estimate_hours": row.estimate_hours,
                "actual_hours": round(row.actual_minutes / 60.0, 2),
            }
            for row in rows
        ]

    def get_open_work_tasks(
        self, min_days_open: int | None = None
    ) -> list[WorkTaskEntity]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.work_tasks)
                .where(t.work_tasks.c.owner_id == self._owner_id)
                .where(t.work_tasks.c.status.notin_(_OPEN_STATES))
                .where(t.work_tasks.c.deleted_at.is_(None))
                .where(t.work_tasks.c.parent_task_id.is_(None))
                .order_by(
                    _WORK_COMMITMENT_ORDER,
                    func.coalesce(t.work_tasks.c.priority_rank, 999999),
                )
            ).all()
            return self._assemble_open(
                c, rows, t.work_tasks, row_to_work_task, min_days_open
            )

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
                .order_by(
                    func.coalesce(t.personal_tasks.c.tier, 99),
                    func.coalesce(t.personal_tasks.c.priority_rank, 999999),
                )
            ).all()
            return self._assemble_open(
                c, rows, t.personal_tasks, row_to_personal_task, min_days_open
            )

    def get_sprint_tasks(self, sprint_id: str | None = None) -> list[WorkTaskEntity]:
        if sprint_id is None:
            return []
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.work_tasks)
                .where(t.work_tasks.c.owner_id == self._owner_id)
                .where(t.work_tasks.c.sprint_id == sprint_id)
                .where(t.work_tasks.c.deleted_at.is_(None))
                .order_by(
                    _WORK_COMMITMENT_ORDER,
                    func.coalesce(t.work_tasks.c.priority_rank, 999999),
                )
            ).all()
        tasks = [row_to_work_task(r) for r in rows]
        for task in tasks:
            task.notes = None
        return tasks

    def get_tasks_updated_on(self, target_date: date) -> dict[str, list]:
        # "Updated on <date>" means the target's local calendar day. Build
        # tz-aware bounds (local midnight → next local midnight) so the compare
        # against timestamptz is correct regardless of the DB session timezone.
        start = datetime.combine(target_date, time.min).astimezone()
        end = datetime.combine(target_date + timedelta(days=1), time.min).astimezone()
        with self._engine.connect() as c:
            has_entry_on = (
                select(t.time_entries.c.id)
                .where(t.time_entries.c.work_task_id == t.work_tasks.c.id)
                .where(t.time_entries.c.date == target_date)
                .exists()
            )
            work_rows = c.execute(
                select(t.work_tasks)
                .where(t.work_tasks.c.owner_id == self._owner_id)
                .where(t.work_tasks.c.deleted_at.is_(None))
                .where(
                    or_(
                        and_(
                            t.work_tasks.c.updated_at >= start,
                            t.work_tasks.c.updated_at < end,
                        ),
                        has_entry_on,
                    )
                )
            ).all()
            personal_rows = c.execute(
                select(t.personal_tasks)
                .where(t.personal_tasks.c.owner_id == self._owner_id)
                .where(t.personal_tasks.c.deleted_at.is_(None))
                .where(t.personal_tasks.c.updated_at >= start)
                .where(t.personal_tasks.c.updated_at < end)
            ).all()

        work_tasks = [row_to_work_task(r) for r in work_rows]
        personal_tasks = [row_to_personal_task(r) for r in personal_rows]
        for task in (*work_tasks, *personal_tasks):
            task.notes = None
        return {"work": work_tasks, "personal": personal_tasks}

    # ---- internal helpers -------------------------------------------------

    def _load_work_task(self, c: Connection, task_id: int) -> WorkTaskEntity | None:
        row = c.execute(
            select(t.work_tasks)
            .where(t.work_tasks.c.id == task_id)
            .where(t.work_tasks.c.owner_id == self._owner_id)
            .where(t.work_tasks.c.deleted_at.is_(None))
        ).one_or_none()
        if row is None:
            return None
        task = row_to_work_task(row)
        child_rows = c.execute(
            select(t.work_tasks)
            .where(t.work_tasks.c.parent_task_id == task_id)
            .where(t.work_tasks.c.deleted_at.is_(None))
        ).all()
        task.children = [row_to_work_task(r) for r in child_rows]
        return task

    def _load_personal_task(
        self, c: Connection, task_id: int
    ) -> PersonalTaskEntity | None:
        row = c.execute(
            select(t.personal_tasks)
            .where(t.personal_tasks.c.id == task_id)
            .where(t.personal_tasks.c.owner_id == self._owner_id)
            .where(t.personal_tasks.c.deleted_at.is_(None))
        ).one_or_none()
        if row is None:
            return None
        task = row_to_personal_task(row)
        child_rows = c.execute(
            select(t.personal_tasks)
            .where(t.personal_tasks.c.parent_task_id == task_id)
            .where(t.personal_tasks.c.deleted_at.is_(None))
        ).all()
        task.children = [row_to_personal_task(r) for r in child_rows]
        return task

    def _assemble_open(self, c, rows, tbl, to_entity, min_days_open):
        tasks = []
        for row in rows:
            task = to_entity(row)
            task.notes = None
            child_rows = c.execute(
                select(tbl)
                .where(tbl.c.parent_task_id == task.id)
                .where(tbl.c.status.notin_(_OPEN_STATES))
                .where(tbl.c.deleted_at.is_(None))
                .order_by(func.coalesce(tbl.c.priority_rank, 999999))
            ).all()
            task.children = [to_entity(r) for r in child_rows]
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

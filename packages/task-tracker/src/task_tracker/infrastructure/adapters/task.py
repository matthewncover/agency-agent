import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta

from task_tracker.application.ports import TaskRepositoryPort
from task_tracker.domain.entities import PersonalTaskEntity
from task_tracker.infrastructure.adapters._converters import row_to_personal_task


class SqliteTaskRepositoryAdapter(TaskRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def create_personal_task(self, task: PersonalTaskEntity) -> PersonalTaskEntity:
        conn = self._conn_factory()
        cur = conn.execute(
            """INSERT INTO personal_tasks
            (title, tier, status, blocked_reason, deadline, parent_task_id,
             is_commitment, commitment_notes, priority_rank, pinned, private, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.title,
                task.tier,
                task.status,
                task.blocked_reason,
                str(task.deadline) if task.deadline else None,
                task.parent_task_id,
                int(task.is_commitment),
                task.commitment_notes,
                task.priority_rank,
                int(task.pinned),
                int(task.private),
                task.notes,
            ),
        )
        conn.commit()
        return _get_personal_task(conn, cur.lastrowid)

    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        return _get_personal_task(self._conn_factory(), task_id)

    def update_personal_task(
        self, task_id: int, fields: dict
    ) -> PersonalTaskEntity | None:
        conn = self._conn_factory()
        if not fields:
            return _get_personal_task(conn, task_id)
        processed = _process_fields(fields)
        set_clause = ", ".join(f"{k} = ?" for k in processed)
        values = list(processed.values()) + [task_id]
        conn.execute(
            f"UPDATE personal_tasks SET {set_clause}"
            " WHERE id = ? AND deleted_at IS NULL",
            values,
        )
        conn.commit()
        return _get_personal_task(conn, task_id)

    def soft_delete_personal_task(self, task_id: int) -> bool:
        conn = self._conn_factory()
        cur = conn.execute(
            "UPDATE personal_tasks"
            " SET deleted_at = datetime('now', 'localtime')"
            " WHERE id = ? AND deleted_at IS NULL",
            (task_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    def restore_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        conn = self._conn_factory()
        conn.execute(
            "UPDATE personal_tasks SET deleted_at = NULL"
            " WHERE id = ? AND deleted_at IS NOT NULL",
            (task_id,),
        )
        conn.commit()
        return _get_personal_task(conn, task_id)

    def search_tasks(
        self,
        query: str,
        include_done: bool = False,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        conn = self._conn_factory()
        like = f"%{query}%"
        where = ["(title LIKE ? OR notes LIKE ?)"]
        params: list = [like, like]
        if not include_done:
            where.append("status != 'done'")
        if not include_deleted:
            where.append("deleted_at IS NULL")
        rows = conn.execute(
            f"""SELECT id, title, tier, status,
                CASE WHEN title LIKE ? THEN 0 ELSE 1 END AS title_rank
            FROM personal_tasks
            WHERE {" AND ".join(where)}
            ORDER BY title_rank, id
            LIMIT ?""",
            [like, *params, limit],
        ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "tier": row["tier"],
                "status": row["status"],
            }
            for row in rows
        ]

    def get_open_personal_tasks(
        self, min_days_open: int | None = None
    ) -> list[PersonalTaskEntity]:
        conn = self._conn_factory()
        rows = conn.execute(
            """SELECT * FROM personal_tasks
            WHERE status NOT IN ('done', 'nuked')
            AND deleted_at IS NULL
            AND parent_task_id IS NULL
            ORDER BY
                COALESCE(tier, 99),
                COALESCE(priority_rank, 999999)""",
        ).fetchall()
        tasks = []
        for row in rows:
            task = row_to_personal_task(row)
            task.notes = None
            children_rows = conn.execute(
                """SELECT * FROM personal_tasks
                WHERE parent_task_id = ?
                AND status NOT IN ('done', 'nuked')
                AND deleted_at IS NULL
                ORDER BY COALESCE(priority_rank, 999999)""",
                (task.id,),
            ).fetchall()
            task.children = [row_to_personal_task(r) for r in children_rows]
            for child in task.children:
                child.notes = None
            if min_days_open is not None:
                if task.days_carried is None or task.days_carried < min_days_open:
                    continue
            tasks.append(task)
        return tasks

    def get_tasks_updated_on(self, target_date: date) -> list[PersonalTaskEntity]:
        conn = self._conn_factory()
        date_str = str(target_date)
        next_date_str = str(target_date + timedelta(days=1))

        rows = conn.execute(
            """SELECT * FROM personal_tasks
            WHERE deleted_at IS NULL
            AND updated_at >= ? AND updated_at < ?""",
            (date_str, next_date_str),
        ).fetchall()

        tasks = [row_to_personal_task(r) for r in rows]
        for task in tasks:
            task.notes = None
        return tasks


def _get_personal_task(
    conn: sqlite3.Connection, task_id: int
) -> PersonalTaskEntity | None:
    row = conn.execute(
        "SELECT * FROM personal_tasks WHERE id = ? AND deleted_at IS NULL",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    task = row_to_personal_task(row)
    children_rows = conn.execute(
        "SELECT * FROM personal_tasks WHERE parent_task_id = ? AND deleted_at IS NULL",
        (task_id,),
    ).fetchall()
    task.children = [row_to_personal_task(r) for r in children_rows]
    return task


def _process_fields(fields: dict) -> dict:
    processed = {}
    for k, v in fields.items():
        if isinstance(v, datetime):
            processed[k] = v.isoformat()
        elif isinstance(v, date):
            processed[k] = str(v)
        elif isinstance(v, bool):
            processed[k] = int(v)
        else:
            processed[k] = v
    return processed

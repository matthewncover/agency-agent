import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta

from task_tracker.application.ports import TaskRepositoryPort
from task_tracker.domain.entities import (
    PersonalTaskEntity,
    WorkTaskEntity,
)
from task_tracker.infrastructure.adapters._converters import (
    row_to_personal_task,
    row_to_work_task,
)


class SqliteTaskRepositoryAdapter(TaskRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def create_work_task(self, task: WorkTaskEntity) -> WorkTaskEntity:
        conn = self._conn_factory()
        cur = conn.execute(
            """INSERT INTO work_tasks
            (title, ods_ticket, sprint_id, commitment_level, jn_bucket,
             status, blocked_reason, estimate_hours, deadline, parent_task_id,
             is_commitment, commitment_notes, priority_rank, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.title,
                task.ods_ticket,
                task.sprint_id,
                task.commitment_level,
                task.jn_bucket,
                task.status,
                task.blocked_reason,
                task.estimate_hours,
                str(task.deadline) if task.deadline else None,
                task.parent_task_id,
                int(task.is_commitment),
                task.commitment_notes,
                task.priority_rank,
                task.notes,
            ),
        )
        conn.commit()
        return _get_work_task(conn, cur.lastrowid)

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

    def get_work_task(self, task_id: int) -> WorkTaskEntity | None:
        return _get_work_task(self._conn_factory(), task_id)

    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None:
        return _get_personal_task(self._conn_factory(), task_id)

    def update_work_task(self, task_id: int, fields: dict) -> WorkTaskEntity | None:
        conn = self._conn_factory()
        if not fields:
            return _get_work_task(conn, task_id)
        processed = _process_fields(fields)
        set_clause = ", ".join(f"{k} = ?" for k in processed)
        values = list(processed.values()) + [task_id]
        conn.execute(
            f"UPDATE work_tasks SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
            values,
        )
        conn.commit()
        return _get_work_task(conn, task_id)

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

    def soft_delete_work_task(self, task_id: int) -> bool:
        conn = self._conn_factory()
        cur = conn.execute(
            "UPDATE work_tasks"
            " SET deleted_at = datetime('now', 'localtime')"
            " WHERE id = ? AND deleted_at IS NULL",
            (task_id,),
        )
        conn.commit()
        return cur.rowcount > 0

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

    def restore_work_task(self, task_id: int) -> WorkTaskEntity | None:
        conn = self._conn_factory()
        conn.execute(
            "UPDATE work_tasks SET deleted_at = NULL"
            " WHERE id = ? AND deleted_at IS NOT NULL",
            (task_id,),
        )
        conn.commit()
        return _get_work_task(conn, task_id)

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
        results: list[dict] = []
        tables = (("work", "work_tasks"), ("personal", "personal_tasks"))
        for task_type, table in tables:
            tier_col = "tier" if task_type == "personal" else "NULL AS tier"
            where = ["(title LIKE ? OR notes LIKE ?)"]
            params: list = [like, like]
            if not include_done:
                where.append("status != 'done'")
            if not include_deleted:
                where.append("deleted_at IS NULL")
            rows = conn.execute(
                f"""SELECT id, title, {tier_col}, status,
                    CASE WHEN title LIKE ? THEN 0 ELSE 1 END AS title_rank
                FROM {table}
                WHERE {" AND ".join(where)}
                ORDER BY title_rank, id""",
                [like, *params],
            ).fetchall()
            for row in rows:
                results.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "tier": row["tier"],
                        "status": row["status"],
                        "type": task_type,
                        "_title_rank": row["title_rank"],
                    }
                )
        results.sort(key=lambda r: (r.pop("_title_rank"), r["type"], r["id"]))
        return results[:limit]

    def get_estimation_data(
        self, n: int | None = None, task_type: str | None = None
    ) -> list[dict]:
        # Only work tasks carry estimate_hours and time entries; personal tasks
        # have neither, so estimation accuracy is inherently work-only.
        if task_type == "personal":
            return []
        conn = self._conn_factory()
        sql = """SELECT wt.id, wt.title, wt.estimate_hours,
                ROUND(COALESCE((
                    SELECT SUM(te.duration_minutes) FROM time_entries te
                    WHERE te.work_task_id = wt.id
                ), 0) / 60.0, 2) AS actual_hours
            FROM work_tasks wt
            WHERE wt.status = 'done'
            AND wt.deleted_at IS NULL
            AND wt.estimate_hours IS NOT NULL
            ORDER BY wt.completed_at DESC, wt.id DESC"""
        params: list = []
        if n is not None:
            sql += " LIMIT ?"
            params.append(n)
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "estimate_hours": row["estimate_hours"],
                "actual_hours": row["actual_hours"],
            }
            for row in rows
        ]

    def get_open_work_tasks(
        self, min_days_open: int | None = None
    ) -> list[WorkTaskEntity]:
        conn = self._conn_factory()
        rows = conn.execute(
            """SELECT * FROM work_tasks
            WHERE status NOT IN ('done', 'nuked')
            AND deleted_at IS NULL
            AND parent_task_id IS NULL
            ORDER BY
                CASE commitment_level
                    WHEN 'sprint_committed' THEN 1
                    WHEN 'sprint_stretch' THEN 2
                    WHEN 'backlog' THEN 3
                    ELSE 4
                END,
                COALESCE(priority_rank, 999999)""",
        ).fetchall()
        tasks = []
        for row in rows:
            task = row_to_work_task(row)
            task.notes = None
            children_rows = conn.execute(
                """SELECT * FROM work_tasks
                WHERE parent_task_id = ?
                AND status NOT IN ('done', 'nuked')
                AND deleted_at IS NULL
                ORDER BY COALESCE(priority_rank, 999999)""",
                (task.id,),
            ).fetchall()
            task.children = [row_to_work_task(r) for r in children_rows]
            for child in task.children:
                child.notes = None
            if min_days_open is not None:
                if task.days_carried is None or task.days_carried < min_days_open:
                    continue
            tasks.append(task)
        return tasks

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

    def get_sprint_tasks(self, sprint_id: str | None = None) -> list[WorkTaskEntity]:
        if sprint_id is None:
            return []
        conn = self._conn_factory()
        rows = conn.execute(
            """SELECT * FROM work_tasks
            WHERE sprint_id = ?
            AND deleted_at IS NULL
            ORDER BY
                CASE commitment_level
                    WHEN 'sprint_committed' THEN 1
                    WHEN 'sprint_stretch' THEN 2
                    ELSE 3
                END,
                COALESCE(priority_rank, 999999)""",
            (sprint_id,),
        ).fetchall()
        tasks = [row_to_work_task(r) for r in rows]
        for t in tasks:
            t.notes = None
        return tasks

    def get_tasks_updated_on(self, target_date: date) -> dict[str, list]:
        conn = self._conn_factory()
        date_str = str(target_date)
        next_date_str = str(target_date + timedelta(days=1))

        work_rows = conn.execute(
            """SELECT DISTINCT wt.* FROM work_tasks wt
            LEFT JOIN time_entries te ON te.work_task_id = wt.id
            WHERE wt.deleted_at IS NULL
            AND (
                (wt.updated_at >= ? AND wt.updated_at < ?)
                OR (te.date = ?)
            )""",
            (date_str, next_date_str, date_str),
        ).fetchall()

        personal_rows = conn.execute(
            """SELECT * FROM personal_tasks
            WHERE deleted_at IS NULL
            AND updated_at >= ? AND updated_at < ?""",
            (date_str, next_date_str),
        ).fetchall()

        work_tasks = [row_to_work_task(r) for r in work_rows]
        personal_tasks = [row_to_personal_task(r) for r in personal_rows]
        for t in work_tasks:
            t.notes = None
        for t in personal_tasks:
            t.notes = None

        return {"work": work_tasks, "personal": personal_tasks}


def _get_work_task(conn: sqlite3.Connection, task_id: int) -> WorkTaskEntity | None:
    row = conn.execute(
        "SELECT * FROM work_tasks WHERE id = ? AND deleted_at IS NULL",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    task = row_to_work_task(row)
    children_rows = conn.execute(
        "SELECT * FROM work_tasks WHERE parent_task_id = ? AND deleted_at IS NULL",
        (task_id,),
    ).fetchall()
    task.children = [row_to_work_task(r) for r in children_rows]
    return task


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

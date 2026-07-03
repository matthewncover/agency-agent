import sqlite3
from collections.abc import Callable

from task_tracker.application.ports import SprintRepositoryPort
from task_tracker.domain.entities import SprintEntity
from task_tracker.infrastructure.adapters._converters import row_to_sprint


class SqliteSprintRepositoryAdapter(SprintRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def get(self, sprint_id: str) -> SprintEntity | None:
        conn = self._conn_factory()
        row = conn.execute(
            "SELECT * FROM sprints WHERE id = ?", (sprint_id,)
        ).fetchone()
        return row_to_sprint(row) if row else None

    def get_active(self) -> SprintEntity | None:
        conn = self._conn_factory()
        row = conn.execute(
            "SELECT * FROM sprints WHERE status = 'active' LIMIT 1"
        ).fetchone()
        return row_to_sprint(row) if row else None

    def create_or_update(self, sprint: SprintEntity) -> SprintEntity:
        conn = self._conn_factory()
        conn.execute(
            """INSERT INTO sprints
            (id, start_date, end_date, status, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                status = excluded.status,
                notes = excluded.notes""",
            (
                sprint.id,
                str(sprint.start_date),
                str(sprint.end_date),
                sprint.status,
                sprint.notes,
            ),
        )
        conn.commit()
        return self.get(sprint.id)

    def deactivate_all(self) -> None:
        conn = self._conn_factory()
        conn.execute(
            "UPDATE sprints SET status = 'completed' WHERE status = 'active'"
        )
        conn.commit()

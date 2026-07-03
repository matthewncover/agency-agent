import sqlite3
from collections.abc import Callable
from datetime import datetime

from task_tracker.application.ports import SystemMetaRepositoryPort
from task_tracker.domain.entities import SystemMetaEntity


class SqliteSystemMetaRepositoryAdapter(SystemMetaRepositoryPort):
    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]):
        self._conn_factory = conn_factory

    def get(self, key: str) -> SystemMetaEntity | None:
        conn = self._conn_factory()
        row = conn.execute(
            "SELECT * FROM system_meta WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get("updated_at") and isinstance(d["updated_at"], str):
            d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return SystemMetaEntity(**d)

    def set(self, key: str, value: str) -> SystemMetaEntity:
        conn = self._conn_factory()
        conn.execute(
            """INSERT INTO system_meta (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value""",
            (key, value),
        )
        conn.commit()
        return self.get(key)

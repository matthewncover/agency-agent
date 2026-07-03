from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from task_tracker.application.ports import SystemMetaRepositoryPort
from task_tracker.domain.entities import SystemMetaEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_system_meta


class PgSystemMetaRepositoryAdapter(SystemMetaRepositoryPort):
    """Global key/value store (single-user MVP), no owner scoping."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self, key: str) -> SystemMetaEntity | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.system_meta).where(t.system_meta.c.key == key)
            ).one_or_none()
        return row_to_system_meta(row) if row else None

    def set(self, key: str, value: str) -> SystemMetaEntity:
        stmt = pg_insert(t.system_meta).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=[t.system_meta.c.key],
            set_={"value": stmt.excluded.value, "updated_at": func.now()},
        )
        with self._engine.begin() as c:
            c.execute(stmt)
        return self.get(key)

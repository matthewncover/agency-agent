from sqlalchemy import Engine, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from task_tracker.application.ports import SprintRepositoryPort
from task_tracker.domain.entities import SprintEntity
from task_tracker.infrastructure import tables as t
from task_tracker.infrastructure.adapters._pg_converters import row_to_sprint


class PgSprintRepositoryAdapter(SprintRepositoryPort):
    """Sprints are global (single-user MVP), so no owner scoping."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self, sprint_id: str) -> SprintEntity | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.sprints).where(t.sprints.c.id == sprint_id)
            ).one_or_none()
        return row_to_sprint(row) if row else None

    def get_active(self) -> SprintEntity | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.sprints).where(t.sprints.c.status == "active").limit(1)
            ).one_or_none()
        return row_to_sprint(row) if row else None

    def create_or_update(self, sprint: SprintEntity) -> SprintEntity:
        with self._engine.begin() as c:
            row = c.execute(
                pg_insert(t.sprints)
                .values(
                    id=sprint.id,
                    start_date=sprint.start_date,
                    end_date=sprint.end_date,
                    status=_enum_val(sprint.status),
                    notes=sprint.notes,
                )
                .on_conflict_do_update(
                    index_elements=[t.sprints.c.id],
                    set_={
                        "start_date": sprint.start_date,
                        "end_date": sprint.end_date,
                        "status": _enum_val(sprint.status),
                        "notes": sprint.notes,
                    },
                )
                .returning(t.sprints)
            ).one()
        return row_to_sprint(row)

    def deactivate_all(self) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.sprints)
                .where(t.sprints.c.status == "active")
                .values(status="completed")
            )


def _enum_val(v):
    return v.value if hasattr(v, "value") else v

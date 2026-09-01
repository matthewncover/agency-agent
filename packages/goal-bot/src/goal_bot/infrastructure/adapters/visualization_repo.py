from datetime import date

from sqlalchemy import Engine, insert, update

from goal_bot.application.ports import VisualizationRepositoryPort
from goal_bot.domain.entities import Visualization
from goal_bot.infrastructure import tables as t


def _viz(row) -> Visualization:
    return Visualization(
        id=row.id,
        person_id=row.person_id,
        text=row.text,
        created_at=row.created_at,
        surfaced_on=row.surfaced_on,
    )


class SqlAlchemyVisualizationRepository(VisualizationRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_visualization(self, person_id: int, text: str) -> Visualization:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.visualization)
                .values(person_id=person_id, text=text)
                .returning(t.visualization)
            ).one()
        return _viz(row)

    def claim_unsurfaced(self, person_id: int, plan_date: date) -> list[Visualization]:
        with self._engine.begin() as c:
            rows = c.execute(
                update(t.visualization)
                .where(
                    t.visualization.c.person_id == person_id,
                    t.visualization.c.surfaced_on.is_(None),
                )
                .values(surfaced_on=plan_date)
                .returning(t.visualization)
            ).all()
        # RETURNING order is not guaranteed — restore capture order here.
        return sorted((_viz(r) for r in rows), key=lambda v: (v.created_at, v.id))

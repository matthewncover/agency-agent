from sqlalchemy import Engine, insert, select

from goal_bot.application.ports import WinRepositoryPort
from goal_bot.domain.entities import WinLogEntry
from goal_bot.infrastructure import tables as t


def _win(row) -> WinLogEntry:
    return WinLogEntry(
        id=row.id,
        person_id=row.person_id,
        goal_id=row.goal_id,
        source=row.source,
        text=row.text,
        created_at=row.created_at,
    )


class SqlAlchemyWinRepository(WinRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_win(self, win: WinLogEntry) -> WinLogEntry:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.win_log)
                .values(
                    person_id=win.person_id,
                    goal_id=win.goal_id,
                    source=win.source,
                    text=win.text,
                )
                .returning(t.win_log)
            ).one()
        return _win(row)

    def list_wins(self, person_id: int, limit: int = 20) -> list[WinLogEntry]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.win_log)
                .where(t.win_log.c.person_id == person_id)
                .order_by(t.win_log.c.created_at.desc())
                .limit(limit)
            ).all()
        return [_win(r) for r in rows]

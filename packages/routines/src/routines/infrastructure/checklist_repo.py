from datetime import date

from sqlalchemy import Connection, Engine, delete, exists, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from routines.application.ports import ChecklistRepositoryPort, StoredChecklist
from routines.domain.checklist import Item
from routines.infrastructure import tables as t


def _ensure_state(c: Connection, person_id: int) -> None:
    c.execute(
        pg_insert(t.person_state)
        .values(person_id=person_id)
        .on_conflict_do_nothing(index_elements=["person_id"])
    )


class SqlAlchemyChecklistRepository(ChecklistRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def load(self, person_id: int) -> StoredChecklist:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.item)
                .where(t.item.c.person_id == person_id)
                .order_by(t.item.c.position, t.item.c.id)
            ).all()
            state = c.execute(
                select(t.person_state).where(t.person_state.c.person_id == person_id)
            ).one_or_none()

        by_id = {r.id: Item(id=r.id, text=r.text, checked=r.checked) for r in rows}
        top: list[Item] = []
        for r in rows:
            if r.parent_id is None:
                top.append(by_id[r.id])
            elif r.parent_id in by_id:
                by_id[r.parent_id].children.append(by_id[r.id])
        return StoredChecklist(
            items=top,
            state_date=state.state_date if state else None,
            sent_date=state.sent_date if state else None,
        )

    def set_checked(
        self, person_id: int, item_id: int, checked: bool, today: date
    ) -> bool:
        child = t.item.alias("child")
        with self._engine.begin() as c:
            _ensure_state(c, person_id)
            state_date = c.execute(
                select(t.person_state.c.state_date)
                .where(t.person_state.c.person_id == person_id)
                .with_for_update()
            ).scalar_one()
            if state_date != today:
                # First tick of a new checklist day: yesterday's ticks go.
                c.execute(
                    update(t.item)
                    .where(t.item.c.person_id == person_id)
                    .values(checked=False)
                )
                c.execute(
                    update(t.person_state)
                    .where(t.person_state.c.person_id == person_id)
                    .values(state_date=today)
                )
            is_parent = exists().where(child.c.parent_id == t.item.c.id)
            result = c.execute(
                update(t.item)
                .where(
                    t.item.c.id == item_id,
                    t.item.c.person_id == person_id,
                    ~is_parent,
                )
                .values(checked=checked)
            )
        return result.rowcount == 1

    def replace_list(self, person_id: int, items: list[Item]) -> None:
        with self._engine.begin() as c:
            keep: set[int] = set()

            def save(item: Item, parent_id: int | None, position: int) -> int:
                values = {
                    "parent_id": parent_id,
                    "position": position,
                    "text": item.text,
                }
                if item.children:
                    values["checked"] = False  # a parent's state is derived
                if item.id is None:
                    item_id = c.execute(
                        insert(t.item)
                        .values(person_id=person_id, **values)
                        .returning(t.item.c.id)
                    ).scalar_one()
                else:
                    item_id = item.id
                    c.execute(
                        update(t.item)
                        .where(t.item.c.id == item_id, t.item.c.person_id == person_id)
                        .values(**values)
                    )
                keep.add(item_id)
                return item_id

            for pos, item in enumerate(items):
                parent_id = save(item, None, pos)
                for child_pos, child in enumerate(item.children):
                    save(child, parent_id, child_pos)

            # After the updates, every kept row points at a kept parent, so
            # the cascade on parent_id only removes children of deleted rows.
            c.execute(
                delete(t.item).where(
                    t.item.c.person_id == person_id, t.item.c.id.not_in(keep)
                )
            )

    def claim_send(self, person_id: int, today: date) -> bool:
        with self._engine.begin() as c:
            _ensure_state(c, person_id)
            result = c.execute(
                update(t.person_state)
                .where(
                    t.person_state.c.person_id == person_id,
                    or_(
                        t.person_state.c.sent_date.is_(None),
                        t.person_state.c.sent_date != today,
                    ),
                )
                .values(sent_date=today)
            )
        return result.rowcount == 1

    def release_send(self, person_id: int, today: date) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.person_state)
                .where(
                    t.person_state.c.person_id == person_id,
                    t.person_state.c.sent_date == today,
                )
                .values(sent_date=None)
            )

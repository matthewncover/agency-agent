from datetime import date

from sqlalchemy import Engine, func, insert, select, update

from goal_bot.application.ports import PlanRepositoryPort
from goal_bot.domain.entities import DailyPlan, DailyPlanItem, PlanItemStatus
from goal_bot.infrastructure import tables as t


def _daily_plan(row) -> DailyPlan:
    return DailyPlan(
        id=row.id,
        person_id=row.person_id,
        plan_date=row.plan_date,
        locked_in_at=row.locked_in_at,
        lock_was_explicit=row.lock_was_explicit,
    )


def _daily_plan_item(row) -> DailyPlanItem:
    return DailyPlanItem(
        id=row.id,
        daily_plan_id=row.daily_plan_id,
        goal_id=row.goal_id,
        goal_version_id=row.goal_version_id,
        status=row.status,
        quantity_actual=float(row.quantity_actual) if row.quantity_actual else None,
        what_shifted=row.what_shifted,
    )


class SqlAlchemyPlanRepository(PlanRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_or_create_plan(self, person_id: int, plan_date: date) -> DailyPlan:
        with self._engine.begin() as c:
            row = c.execute(
                select(t.daily_plan)
                .where(t.daily_plan.c.person_id == person_id)
                .where(t.daily_plan.c.plan_date == plan_date)
            ).one_or_none()
            if not row:
                row = c.execute(
                    insert(t.daily_plan)
                    .values(person_id=person_id, plan_date=plan_date)
                    .returning(t.daily_plan)
                ).one()
        return _daily_plan(row)

    def get_plan_items(self, daily_plan_id: int) -> list[DailyPlanItem]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.daily_plan_item)
                .where(t.daily_plan_item.c.daily_plan_id == daily_plan_id)
            ).all()
        return [_daily_plan_item(r) for r in rows]

    def add_plan_item(self, item: DailyPlanItem) -> DailyPlanItem:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.daily_plan_item)
                .values(
                    daily_plan_id=item.daily_plan_id,
                    goal_id=item.goal_id,
                    goal_version_id=item.goal_version_id,
                    status=item.status,
                    quantity_actual=item.quantity_actual,
                    what_shifted=item.what_shifted,
                )
                .returning(t.daily_plan_item)
            ).one()
        return _daily_plan_item(row)

    def set_item_outcome(
        self,
        item_id: int,
        status: PlanItemStatus,
        quantity_actual: float | None = None,
    ) -> DailyPlanItem:
        with self._engine.begin() as c:
            c.execute(
                update(t.daily_plan_item)
                .where(t.daily_plan_item.c.id == item_id)
                .values(status=status, quantity_actual=quantity_actual)
            )
            row = c.execute(
                select(t.daily_plan_item)
                .where(t.daily_plan_item.c.id == item_id)
            ).one()
        return _daily_plan_item(row)

    def set_item_reflection(self, item_id: int, what_shifted: str) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.daily_plan_item)
                .where(t.daily_plan_item.c.id == item_id)
                .values(what_shifted=what_shifted)
            )

    def lock_in(self, daily_plan_id: int, explicit: bool) -> DailyPlan:
        with self._engine.begin() as c:
            c.execute(
                update(t.daily_plan)
                .where(t.daily_plan.c.id == daily_plan_id)
                .values(locked_in_at=func.now(), lock_was_explicit=explicit)
            )
            row = c.execute(
                select(t.daily_plan).where(t.daily_plan.c.id == daily_plan_id)
            ).one()
        return _daily_plan(row)

    def get_plan_for_date(
        self, person_id: int, plan_date: date
    ) -> tuple[DailyPlan, list[DailyPlanItem]] | None:
        with self._engine.connect() as c:
            plan_row = c.execute(
                select(t.daily_plan)
                .where(t.daily_plan.c.person_id == person_id)
                .where(t.daily_plan.c.plan_date == plan_date)
            ).one_or_none()
            if not plan_row:
                return None
            item_rows = c.execute(
                select(t.daily_plan_item)
                .where(t.daily_plan_item.c.daily_plan_id == plan_row.id)
            ).all()
        return _daily_plan(plan_row), [_daily_plan_item(r) for r in item_rows]

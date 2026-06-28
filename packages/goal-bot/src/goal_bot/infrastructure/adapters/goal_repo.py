from datetime import date

from sqlalchemy import Engine, func, insert, or_, select, update

from goal_bot.application.ports import GoalRepositoryPort
from goal_bot.domain.entities import Chapter, Goal, GoalVersion
from goal_bot.infrastructure import tables as t


def _chapter(row) -> Chapter:
    return Chapter(
        id=row.id,
        owner_profile_id=row.owner_profile_id,
        label=row.label,
        start_date=row.start_date,
        end_date=row.end_date,
    )


def _goal(row) -> Goal:
    return Goal(
        id=row.id,
        owner_profile_id=row.owner_profile_id,
        chapter_id=row.chapter_id,
        title=row.title,
        created_at=row.created_at,
        archived_at=row.archived_at,
    )


def _goal_version(row) -> GoalVersion:
    return GoalVersion(
        id=row.id,
        goal_id=row.goal_id,
        version_no=row.version_no,
        level=row.level,
        definition=row.definition,
        why=row.why,
        recurrence_type=row.recurrence_type,
        recurrence_config=row.recurrence_config,
        completion_type=row.completion_type,
        target_quantity=float(row.target_quantity) if row.target_quantity else None,
        quantity_unit=row.quantity_unit,
        task_ref_source=row.task_ref_source,
        task_ref_id=row.task_ref_id,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        lifecycle=row.lifecycle,
    )


class SqlAlchemyGoalRepository(GoalRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_chapter(self, chapter: Chapter) -> Chapter:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.chapter)
                .values(
                    owner_profile_id=chapter.owner_profile_id,
                    label=chapter.label,
                    start_date=chapter.start_date,
                    end_date=chapter.end_date,
                )
                .returning(t.chapter)
            ).one()
        return _chapter(row)

    def get_active_chapter(
        self, owner_profile_id: int, on: date
    ) -> Chapter | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.chapter)
                .where(t.chapter.c.owner_profile_id == owner_profile_id)
                .where(t.chapter.c.start_date <= on)
                .where(t.chapter.c.end_date >= on)
                .limit(1)
            ).one_or_none()
        return _chapter(row) if row else None

    def create_goal(self, goal: Goal) -> Goal:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.goal)
                .values(
                    owner_profile_id=goal.owner_profile_id,
                    chapter_id=goal.chapter_id,
                    title=goal.title,
                )
                .returning(t.goal)
            ).one()
            c.execute(insert(t.goal_state).values(goal_id=row.id))
        return _goal(row)

    def create_goal_version(self, version: GoalVersion) -> GoalVersion:
        vals: dict = {
            "goal_id": version.goal_id,
            "level": version.level,
            "definition": version.definition,
            "why": version.why,
            "recurrence_type": version.recurrence_type,
            "recurrence_config": version.recurrence_config,
            "completion_type": version.completion_type,
            "target_quantity": version.target_quantity,
            "quantity_unit": version.quantity_unit,
            "task_ref_source": version.task_ref_source,
            "task_ref_id": version.task_ref_id,
            "lifecycle": version.lifecycle,
        }
        if version.effective_from is not None:
            vals["effective_from"] = version.effective_from
        if version.effective_to is not None:
            vals["effective_to"] = version.effective_to
        with self._engine.begin() as c:
            # version_no is server-assigned per (goal_id, level): a bar change is
            # a new version in that level's own lineage (spec §5.2 / OQ-14).
            if version.version_no is not None:
                vals["version_no"] = version.version_no
            else:
                prev_max = c.execute(
                    select(func.max(t.goal_version.c.version_no))
                    .where(t.goal_version.c.goal_id == version.goal_id)
                    .where(t.goal_version.c.level == version.level)
                ).scalar()
                vals["version_no"] = (prev_max or 0) + 1
            # Close the prior current version at this (goal, level) so a bar
            # bump leaves exactly one effective row per level (§5.2). Old
            # daily_plan_items stay pinned to the closed version (OQ-14).
            c.execute(
                update(t.goal_version)
                .where(t.goal_version.c.goal_id == version.goal_id)
                .where(t.goal_version.c.level == version.level)
                .where(t.goal_version.c.effective_to.is_(None))
                .values(effective_to=func.now())
            )
            row = c.execute(
                insert(t.goal_version).values(**vals)
                .returning(t.goal_version)
            ).one()
            if version.obstacles:
                c.execute(
                    insert(t.anticipated_obstacle),
                    [
                        {"goal_version_id": row.id, "text": text}
                        for text in version.obstacles
                    ],
                )
        result = _goal_version(row)
        result.obstacles = list(version.obstacles)
        return result

    def get_goal_detail(
        self, goal_id: int
    ) -> tuple[Goal, list[GoalVersion]] | None:
        with self._engine.connect() as c:
            g_row = c.execute(
                select(t.goal).where(t.goal.c.id == goal_id)
            ).one_or_none()
            if not g_row:
                return None
            v_rows = c.execute(
                select(t.goal_version)
                .where(t.goal_version.c.goal_id == goal_id)
            ).all()
            versions = [_goal_version(r) for r in v_rows]
            if versions:
                obs_rows = c.execute(
                    select(t.anticipated_obstacle)
                    .where(
                        t.anticipated_obstacle.c.goal_version_id.in_(
                            [v.id for v in versions]
                        )
                    )
                ).all()
                by_version: dict[int, list[str]] = {}
                for o in obs_rows:
                    by_version.setdefault(o.goal_version_id, []).append(o.text)
                for v in versions:
                    v.obstacles = by_version.get(v.id, [])
        return _goal(g_row), versions

    def get_full_goal_list(
        self, owner_profile_id: int, on: date
    ) -> list[Goal]:
        active = self.get_active_chapter(owner_profile_id, on)
        active_chapter_id = active.id if active else None

        if active_chapter_id is not None:
            chapter_cond = or_(
                t.goal.c.chapter_id == active_chapter_id,
                t.goal.c.chapter_id.is_(None),
            )
        else:
            chapter_cond = t.goal.c.chapter_id.is_(None)

        has_active_version = (
            select(t.goal_version.c.id)
            .where(t.goal_version.c.goal_id == t.goal.c.id)
            .where(t.goal_version.c.lifecycle == "active")
            .exists()
        )

        with self._engine.connect() as c:
            rows = c.execute(
                select(t.goal)
                .where(t.goal.c.owner_profile_id == owner_profile_id)
                .where(chapter_cond)
                .where(t.goal.c.archived_at.is_(None))
                .where(has_active_version)
            ).all()
        return [_goal(r) for r in rows]

    def update_goal(self, goal_id: int, fields: dict) -> Goal | None:
        with self._engine.begin() as c:
            c.execute(
                update(t.goal).where(t.goal.c.id == goal_id).values(**fields)
            )
            row = c.execute(
                select(t.goal).where(t.goal.c.id == goal_id)
            ).one_or_none()
        return _goal(row) if row else None

from datetime import date, datetime

from sqlalchemy import Engine, func, insert, or_, select, update

from goal_bot.application.ports import GoalRepositoryPort
from goal_bot.domain.entities import (
    Chapter,
    Goal,
    GoalState,
    GoalVersion,
    Insight,
    RotationGroup,
)
from goal_bot.infrastructure import tables as t


def _rotation_group(row) -> RotationGroup:
    return RotationGroup(
        id=row.id,
        owner_profile_id=row.owner_profile_id,
        name=row.name,
        sequence=row.sequence,
        rotation_index=row.rotation_index,
        last_completed_at=row.last_completed_at,
        archived_at=row.archived_at,
    )


def _chapter(row) -> Chapter:
    return Chapter(
        id=row.id,
        owner_profile_id=row.owner_profile_id,
        label=row.label,
        preamble=row.preamble,
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


def _insert_goal_row(c, goal: Goal) -> Goal:
    """Insert a goal + its seed goal_state on an open connection."""
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


def _insert_goal_version_row(c, version: GoalVersion) -> GoalVersion:
    """Insert a goal_version (+ obstacles) on an open connection, assigning
    version_no per (goal_id, level) and closing the prior current version."""
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
    # version_no is server-assigned per (goal_id, level): a bar change is a new
    # version in that level's own lineage (spec §5.2 / OQ-14).
    if version.version_no is not None:
        vals["version_no"] = version.version_no
    else:
        prev_max = c.execute(
            select(func.max(t.goal_version.c.version_no))
            .where(t.goal_version.c.goal_id == version.goal_id)
            .where(t.goal_version.c.level == version.level)
        ).scalar()
        vals["version_no"] = (prev_max or 0) + 1
    # Close the prior current version at this (goal, level) so a bar bump leaves
    # exactly one effective row per level (§5.2). Old daily_plan_items stay
    # pinned to the closed version (OQ-14).
    c.execute(
        update(t.goal_version)
        .where(t.goal_version.c.goal_id == version.goal_id)
        .where(t.goal_version.c.level == version.level)
        .where(t.goal_version.c.effective_to.is_(None))
        .values(effective_to=func.now())
    )
    row = c.execute(
        insert(t.goal_version).values(**vals).returning(t.goal_version)
    ).one()
    if version.obstacles:
        c.execute(
            insert(t.anticipated_obstacle),
            [{"goal_version_id": row.id, "text": text} for text in version.obstacles],
        )
    result = _goal_version(row)
    result.obstacles = list(version.obstacles)
    return result


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
                    preamble=chapter.preamble,
                    start_date=chapter.start_date,
                    end_date=chapter.end_date,
                )
                .returning(t.chapter)
            ).one()
        return _chapter(row)

    def get_active_chapter(self, owner_profile_id: int, on: date) -> Chapter | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.chapter)
                .where(t.chapter.c.owner_profile_id == owner_profile_id)
                .where(t.chapter.c.start_date <= on)
                .where(t.chapter.c.end_date >= on)
                .limit(1)
            ).one_or_none()
        return _chapter(row) if row else None

    def get_chapter(self, chapter_id: int) -> Chapter | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.chapter).where(t.chapter.c.id == chapter_id)
            ).one_or_none()
        return _chapter(row) if row else None

    def create_goal(self, goal: Goal) -> Goal:
        with self._engine.begin() as c:
            return _insert_goal_row(c, goal)

    def create_goal_version(self, version: GoalVersion) -> GoalVersion:
        with self._engine.begin() as c:
            return _insert_goal_version_row(c, version)

    def create_goals_with_versions(
        self, goals: list[tuple[Goal, list[GoalVersion]]]
    ) -> list[tuple[Goal, list[GoalVersion]]]:
        """Create N new goals, each with its versions + obstacles, atomically."""
        out: list[tuple[Goal, list[GoalVersion]]] = []
        with self._engine.begin() as c:
            for goal, versions in goals:
                saved_goal = _insert_goal_row(c, goal)
                saved_versions = [
                    _insert_goal_version_row(
                        c, v.model_copy(update={"goal_id": saved_goal.id})
                    )
                    for v in versions
                ]
                out.append((saved_goal, saved_versions))
        return out

    def create_goal_versions(self, versions: list[GoalVersion]) -> list[GoalVersion]:
        """Add N versions to existing goals atomically (re-ingest bar changes)."""
        with self._engine.begin() as c:
            return [_insert_goal_version_row(c, v) for v in versions]

    def get_goal_detail(self, goal_id: int) -> tuple[Goal, list[GoalVersion]] | None:
        with self._engine.connect() as c:
            g_row = c.execute(
                select(t.goal).where(t.goal.c.id == goal_id)
            ).one_or_none()
            if not g_row:
                return None
            v_rows = c.execute(
                select(t.goal_version).where(t.goal_version.c.goal_id == goal_id)
            ).all()
            versions = [_goal_version(r) for r in v_rows]
            if versions:
                obs_rows = c.execute(
                    select(t.anticipated_obstacle).where(
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

    def get_full_goal_list(self, owner_profile_id: int, on: date) -> list[Goal]:
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

    def get_goals_for_chapter(
        self, chapter_id: int, owner_profile_id: int | None = None
    ) -> list[Goal]:
        stmt = select(t.goal).where(t.goal.c.chapter_id == chapter_id)
        if owner_profile_id is not None:
            stmt = stmt.where(t.goal.c.owner_profile_id == owner_profile_id)
        with self._engine.connect() as c:
            rows = c.execute(stmt.order_by(t.goal.c.id)).all()
        return [_goal(r) for r in rows]

    def list_all_goals(self, owner_profile_id: int) -> list[Goal]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.goal)
                .where(t.goal.c.owner_profile_id == owner_profile_id)
                .order_by(t.goal.c.id)
            ).all()
        return [_goal(r) for r in rows]

    def archive_chapter_goals(self, chapter_id: int) -> list[int]:
        with self._engine.begin() as c:
            rows = c.execute(
                update(t.goal)
                .where(t.goal.c.chapter_id == chapter_id)
                .where(t.goal.c.archived_at.is_(None))
                .values(archived_at=func.now())
                .returning(t.goal.c.id)
            ).all()
        return [r.id for r in rows]

    def update_goal(self, goal_id: int, fields: dict) -> Goal | None:
        with self._engine.begin() as c:
            c.execute(update(t.goal).where(t.goal.c.id == goal_id).values(**fields))
            row = c.execute(select(t.goal).where(t.goal.c.id == goal_id)).one_or_none()
        return _goal(row) if row else None

    def advance_carry_over(self, goal_id: int) -> int:
        with self._engine.begin() as c:
            new_count = c.execute(
                update(t.goal_state)
                .where(t.goal_state.c.goal_id == goal_id)
                .values(carry_over_count=t.goal_state.c.carry_over_count + 1)
                .returning(t.goal_state.c.carry_over_count)
            ).scalar()
        return int(new_count)

    def reset_carry_over(self, goal_id: int) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.goal_state)
                .where(t.goal_state.c.goal_id == goal_id)
                .values(carry_over_count=0)
            )

    def get_carry_over_count(self, goal_id: int) -> int:
        with self._engine.connect() as c:
            count = c.execute(
                select(t.goal_state.c.carry_over_count).where(
                    t.goal_state.c.goal_id == goal_id
                )
            ).scalar()
        return int(count) if count is not None else 0

    def get_goal_state(self, goal_id: int) -> GoalState:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.goal_state).where(t.goal_state.c.goal_id == goal_id)
            ).one_or_none()
        if row is None:
            return GoalState(goal_id=goal_id)
        return GoalState(
            goal_id=row.goal_id,
            rotation_index=row.rotation_index,
            last_completed_at=row.last_completed_at,
            carry_over_count=row.carry_over_count,
        )

    def advance_rotation(self, goal_id: int, new_index: int, when: datetime) -> int:
        # new_index is computed by the caller from the SURFACED slot (domain
        # walk, ADR-0016) — never derived here from the raw stored pointer.
        with self._engine.begin() as c:
            c.execute(
                update(t.goal_state)
                .where(t.goal_state.c.goal_id == goal_id)
                .values(rotation_index=new_index, last_completed_at=when)
            )
        return new_index

    def set_last_completed(self, goal_id: int, when: datetime) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.goal_state)
                .where(t.goal_state.c.goal_id == goal_id)
                .values(last_completed_at=when)
            )

    def set_goal_archived(self, goal_id: int, when: datetime | None) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.goal).where(t.goal.c.id == goal_id).values(archived_at=when)
            )

    def set_versions_lifecycle(
        self, goal_id: int, from_state: str, to_state: str
    ) -> int:
        """Flip the goal's versions from one lifecycle state to another
        (pause: active→paused; activate: paused→active). Returns rows changed."""
        with self._engine.begin() as c:
            res = c.execute(
                update(t.goal_version)
                .where(t.goal_version.c.goal_id == goal_id)
                .where(t.goal_version.c.lifecycle == from_state)
                .values(lifecycle=to_state)
            )
        return res.rowcount

    def set_rotation_pointer(self, goal_id: int, position: int) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.goal_state)
                .where(t.goal_state.c.goal_id == goal_id)
                .values(rotation_index=position)
            )

    # --- rotation groups (ADR-0016) ---

    def create_rotation_group(self, group: RotationGroup) -> RotationGroup:
        with self._engine.begin() as c:
            row = c.execute(
                insert(t.rotation_group)
                .values(
                    owner_profile_id=group.owner_profile_id,
                    name=group.name,
                    sequence=group.sequence,
                    rotation_index=group.rotation_index,
                )
                .returning(t.rotation_group)
            ).one()
        return _rotation_group(row)

    def get_rotation_group(self, group_id: int) -> RotationGroup | None:
        with self._engine.connect() as c:
            row = c.execute(
                select(t.rotation_group).where(t.rotation_group.c.id == group_id)
            ).one_or_none()
        return _rotation_group(row) if row else None

    def list_rotation_groups(self, owner_profile_id: int) -> list[RotationGroup]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.rotation_group)
                .where(t.rotation_group.c.owner_profile_id == owner_profile_id)
                .where(t.rotation_group.c.archived_at.is_(None))
                .order_by(t.rotation_group.c.id)
            ).all()
        return [_rotation_group(r) for r in rows]

    def get_rotation_group_for_goal(self, goal_id: int) -> RotationGroup | None:
        # jsonb containment ({"goal_id": N} ∈ sequence) — served by the gin
        # index; at most one active group per goal (app-enforced at create).
        with self._engine.connect() as c:
            row = c.execute(
                select(t.rotation_group)
                .where(t.rotation_group.c.sequence.contains([{"goal_id": goal_id}]))
                .where(t.rotation_group.c.archived_at.is_(None))
                .order_by(t.rotation_group.c.id)
                .limit(1)
            ).one_or_none()
        return _rotation_group(row) if row else None

    def advance_rotation_group(
        self, group_id: int, new_index: int, when: datetime
    ) -> int:
        with self._engine.begin() as c:
            c.execute(
                update(t.rotation_group)
                .where(t.rotation_group.c.id == group_id)
                .values(rotation_index=new_index, last_completed_at=when)
            )
        return new_index

    def set_rotation_group_pointer(self, group_id: int, position: int) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.rotation_group)
                .where(t.rotation_group.c.id == group_id)
                .values(rotation_index=position)
            )

    def set_rotation_group_archived(self, group_id: int, when: datetime | None) -> None:
        with self._engine.begin() as c:
            c.execute(
                update(t.rotation_group)
                .where(t.rotation_group.c.id == group_id)
                .values(archived_at=when)
            )

    def list_active_insights(self, person_id: int) -> list[Insight]:
        with self._engine.connect() as c:
            rows = c.execute(
                select(t.insight)
                .where(t.insight.c.person_id == person_id)
                .where(t.insight.c.status == "active")
                .order_by(t.insight.c.id)
            ).all()
        return [
            Insight(
                id=r.id,
                person_id=r.person_id,
                content=r.content,
                status=r.status,
                derived_from=r.derived_from,
            )
            for r in rows
        ]

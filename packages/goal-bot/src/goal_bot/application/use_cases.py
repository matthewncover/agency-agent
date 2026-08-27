from dataclasses import dataclass
from datetime import date, datetime

from agency_profile.application.ports import ProfileRepositoryPort
from agency_profile.domain.entities import ProfileKind
from task_tracker.application.query_client import TaskQueryClient

from goal_bot.application.ports import (
    GoalRepositoryPort,
    PlanRepositoryPort,
    WinRepositoryPort,
)
from goal_bot.domain.entities import (
    Chapter,
    Goal,
    GoalVersion,
    PlanItemStatus,
    RecurrenceType,
    RotationGroup,
    WinLogEntry,
)
from goal_bot.domain.recurrence import (
    accumulation_reached,
    is_pointer_recurrence,
    rotation_current_index,
    rotation_days_elapsed,
    rotation_due_index,
    rotation_group_due_index,
    rotation_group_index_of_goal,
    rotation_group_member_ids,
    rotation_next_index,
)

# Tags are intentionally absent: there is no tag column on `goal` and no
# tag/goal_tag write path yet (deferred per goal-markdown.md §4). Listing it
# here would let a write pass validation and then crash in the repo.
_GOAL_IDENTITY_FIELDS = {"title", "chapter_id", "archived_at"}


@dataclass
class GoalUseCases:
    goals: GoalRepositoryPort
    plans: PlanRepositoryPort
    wins: WinRepositoryPort
    # Optional — enables shared (group-goal) completion propagation (B7). When
    # absent, log_outcome behaves single-user (no fan-out side effect).
    profiles: ProfileRepositoryPort | None = None
    # Optional — enables task_ref validation on version creation (ADR-0018).
    # When absent, refs are stored unvalidated (single-package test setups).
    tasks: TaskQueryClient | None = None

    # --- authoring ---

    def create_chapter(
        self,
        owner: int,
        start: date,
        end: date,
        label: str | None,
        preamble: str | None = None,
    ) -> int:
        return self.goals.create_chapter(
            Chapter(
                owner_profile_id=owner,
                start_date=start,
                end_date=end,
                label=label,
                preamble=preamble,
            )
        ).id

    def create_goal(self, owner: int, title: str, chapter_id: int | None) -> int:
        return self.goals.create_goal(
            Goal(owner_profile_id=owner, title=title, chapter_id=chapter_id)
        ).id

    def create_goal_version(self, **kw) -> int:
        version = GoalVersion(**kw)
        self._validate_task_ref(version)
        return self.goals.create_goal_version(version).id

    def create_goals(self, owner: int, goals: list[dict]) -> list[dict]:
        """Batch-create new goals, each with its versions + obstacles, atomically.
        Each goal: {title, chapter_id?, versions: [version-kwargs ...]}."""
        specs: list[tuple[Goal, list[GoalVersion]]] = []
        for g in goals:
            goal = Goal(
                owner_profile_id=owner,
                title=g["title"],
                chapter_id=g.get("chapter_id"),
            )
            versions = [GoalVersion(goal_id=None, **v) for v in g["versions"]]
            for v in versions:
                self._validate_task_ref(v, owner=owner)
            specs.append((goal, versions))
        saved = self.goals.create_goals_with_versions(specs)
        return [
            {
                "gid": goal.id,
                "title": goal.title,
                "versions": [
                    {"level": v.level, "version_id": v.id, "version_no": v.version_no}
                    for v in versions
                ],
            }
            for goal, versions in saved
        ]

    def create_goal_versions(self, versions: list[dict]) -> list[int]:
        """Batch-add versions to existing goals atomically. Each dict carries a
        goal_id (re-ingest bar changes)."""
        objs = [GoalVersion(**v) for v in versions]
        for v in objs:
            self._validate_task_ref(v)
        return [v.id for v in self.goals.create_goal_versions(objs)]

    def _validate_task_ref(
        self, version: GoalVersion, owner: int | None = None
    ) -> None:
        """Reject a task_ref that doesn't resolve for the goal's owner. Because
        get_task_status answers None for private tasks (ADR-0018), this also
        blocks new refs to private tasks — indistinguishable from nonexistent
        ones by design. No-op when no task client is wired."""
        if version.task_ref_source is None and version.task_ref_id is None:
            return
        if version.task_ref_source is None or version.task_ref_id is None:
            raise ValueError("task_ref requires both task_ref_source and task_ref_id")
        if self.tasks is None:
            return
        if owner is None:
            detail = self.goals.get_goal_detail(version.goal_id)
            if detail is None:
                raise ValueError(f"no goal {version.goal_id}")
            owner = detail[0].owner_profile_id
        status = self.tasks.get_task_status(
            str(version.task_ref_source), version.task_ref_id, owner
        )
        if status is None:
            raise ValueError(
                f"task_ref ({version.task_ref_source}, {version.task_ref_id}) "
                f"does not resolve for owner {owner} — the task doesn't exist, "
                "belongs to someone else, or is private"
            )

    def update_goal(self, goal_id: int, fields: dict) -> dict:
        bad = set(fields) - _GOAL_IDENTITY_FIELDS
        if bad:
            raise ValueError(
                "update_goal accepts only title/chapter_id/archived_at; "
                f"rejected: {sorted(bad)}"
            )
        g = self.goals.update_goal(goal_id, fields)
        return g.model_dump()

    # --- ritual writes ---

    def log_outcome(
        self,
        daily_plan_item_id: int,
        status: str,
        quantity_actual: float | None = None,
    ) -> dict:
        st = PlanItemStatus(status)
        _allowed = {
            PlanItemStatus.DONE,
            PlanItemStatus.PARTIAL,
            PlanItemStatus.NOT_DONE,
        }
        if st not in _allowed:
            raise ValueError("log_outcome accepts only done|partial|not_done")

        existing = self.plans.get_item(daily_plan_item_id)
        if existing is None:
            raise ValueError(f"no plan item {daily_plan_item_id}")
        version = self._version_of(existing.goal_id, existing.goal_version_id)
        recurrence = version.recurrence_type if version else None

        # Rotation-group membership (ADR-0016): fetched once — it extends the
        # backdating gate below and drives the shared-pointer advance on done.
        group = self.goals.get_rotation_group_for_goal(existing.goal_id)
        plan_date = self.plans.get_item_plan_date(daily_plan_item_id)

        # Backdating restriction (mcp-tools §3.1/§5): a pointer's state can't be
        # recomputed from a past-dated log, so backdating is rejected for
        # interval/rotation goals AND rotation-group members — pointer correction
        # is a separate explicit tool (set_rotation_pointer /
        # set_rotation_group_pointer, B6). Non-pointer goals backdate freely.
        if is_pointer_recurrence(recurrence) or group is not None:
            if plan_date is not None and plan_date < date.today():
                raise ValueError(
                    "backdating is restricted to non-pointer goals; "
                    "interval/rotation pointer correction uses "
                    "set_rotation_pointer / set_rotation_group_pointer"
                )

        item = self.plans.set_item_outcome(daily_plan_item_id, st, quantity_actual)

        # Side effects — the carry-over counter (mcp-tools §4.1) and the
        # pointer-advance for interval/rotation (mcp-tools §3.1). All fire
        # exclusively from an engaged self-report; silence emits no tool call at
        # all (NULL-TOLERANCE). Accumulation goals are exempt entirely: "didn't
        # paint today" is structurally not a miss (§4.3).
        if recurrence != RecurrenceType.ACCUMULATION:
            if st == PlanItemStatus.NOT_DONE:
                self.goals.advance_carry_over(item.goal_id)
            elif st == PlanItemStatus.DONE:
                # A win halts the chain; `partial` leaves the counter untouched.
                self.goals.reset_carry_over(item.goal_id)
                self._advance_pointer_on_done(
                    item.goal_id, version, group, plan_date or date.today()
                )
                # A DONE one-off is complete — archive the goal so it stops
                # surfacing. This is bookkeeping on an explicit self-report,
                # not an auto-drop (non-negotiable 5 protects the unfinished);
                # reversible via unarchive. Derived-win surfacing is unaffected
                # (it reads yesterday's plan items by id). `partial` archives
                # nothing.
                if recurrence == RecurrenceType.ONEOFF:
                    self.goals.set_goal_archived(item.goal_id, datetime.now())

        # Group-goal shared completion (behavior-spec §6): if this goal is
        # group-owned and it was completed, it's "done for both" — mark the
        # other members' items for the same goal on the same date. Never
        # comparative, never surfaced as a scoreboard.
        if st == PlanItemStatus.DONE:
            self._propagate_shared_completion(item)

        return item.model_dump()

    def revert_outcome(self, daily_plan_item_id: int) -> dict:
        """Undo a mis-logged outcome: restore the item to `planned` and clear
        quantity_actual. Correction-only, on the user's explicit say-so. Does
        NOT rewind rotation/interval pointers (set_rotation_pointer /
        set_rotation_group_pointer are the correction tools there), does NOT
        restore the carry-over counter (no history to restore from; the drift
        errs non-punitive), and never touches a partner's propagated
        shared-completion item — they may genuinely have done it."""
        existing = self.plans.get_item(daily_plan_item_id)
        if existing is None:
            raise ValueError(f"no plan item {daily_plan_item_id}")
        prior = existing.status
        if prior == PlanItemStatus.PLANNED:
            return existing.model_dump()  # nothing to undo

        item = self.plans.set_item_outcome(
            daily_plan_item_id, PlanItemStatus.PLANNED, None
        )

        # A done one-off archived itself inside log_outcome; reverting the done
        # un-archives it so the goal surfaces again.
        if prior == PlanItemStatus.DONE:
            version = self._version_of(existing.goal_id, existing.goal_version_id)
            if version is not None and version.recurrence_type == RecurrenceType.ONEOFF:
                self.goals.set_goal_archived(item.goal_id, None)

        return item.model_dump()

    def _propagate_shared_completion(self, item) -> None:
        if self.profiles is None:
            return
        detail = self.goals.get_goal_detail(item.goal_id)
        if not detail:
            return
        goal = detail[0]
        owner = goal.owner_profile_id
        if self.profiles.get_kind(owner) != ProfileKind.GROUP:
            return  # individual goal — nothing to share
        plan_date = self.plans.get_item_plan_date(item.id)
        if plan_date is None:
            return
        for member_id in self.profiles.list_group_members(owner):
            member_plan = self.plans.get_or_create_plan(member_id, plan_date)
            member_item = self.plans.get_or_create_item(
                member_plan.id, item.goal_id, item.goal_version_id
            )
            if member_item.status != PlanItemStatus.DONE:
                self.plans.set_item_outcome(member_item.id, PlanItemStatus.DONE)

    def _advance_pointer_on_done(
        self,
        goal_id: int,
        version: GoalVersion | None,
        group,
        on: date,
    ) -> None:
        """Completion side effect for pointer goals (mcp-tools §3.1):
        rotation steps its pointer; interval resets its clock. A rotation-group
        member additionally advances the group's shared pointer (ADR-0016).
        All walks/stamps key off `on` — the item's plan_date (== today for
        pointer goals, whose backdating is rejected upstream)."""
        if version is None:
            return
        # Noon keeps the stamp date-exact for the walk (which only reads the
        # date) without pretending to know a completion time.
        when = datetime(on.year, on.month, on.day, 12)

        # Rotation group first (ADR-0016): advance the shared pointer one past
        # the entry this `done` belongs to. The member's own recurrence side
        # effect below still fires (inert for scheduling while the group is
        # active, but it keeps e.g. an interval member's clock honest for
        # graceful degradation if the group is later archived).
        if group is not None:
            seq = group.sequence
            idx = rotation_group_due_index(
                seq,
                group.rotation_index,
                rotation_days_elapsed(group.last_completed_at, on),
            )
            if idx is None or seq[idx].get("goal_id") != goal_id:
                # Off-schedule done (did it early on a rest day, or a second
                # member logged) — resolve to this goal's next slot instead.
                idx = rotation_group_index_of_goal(seq, group.rotation_index, goal_id)
            if idx is not None:
                self.goals.advance_rotation_group(
                    group.id, rotation_next_index(idx, len(seq)), when
                )

        if version.recurrence_type == RecurrenceType.ROTATION:
            cfg = version.recurrence_config
            seq = cfg.get("sequence", [])
            state = self.goals.get_goal_state(goal_id)
            # Advance from the SURFACED slot, not the raw stored pointer —
            # the stored pointer may sit on a rest label behind the session
            # that actually surfaced (ADR-0016 bug 2).
            idx = rotation_due_index(
                seq,
                state.rotation_index,
                cfg.get("rest_labels"),
                rotation_days_elapsed(state.last_completed_at, on),
            )
            if idx is None:
                idx = rotation_current_index(
                    seq, state.rotation_index, cfg.get("rest_labels")
                )
            if idx is not None:
                self.goals.advance_rotation(
                    goal_id, rotation_next_index(idx, len(seq)), when
                )
        elif version.recurrence_type == RecurrenceType.INTERVAL:
            self.goals.set_last_completed(goal_id, when)

    def _version_of(self, goal_id: int, goal_version_id: int) -> GoalVersion | None:
        detail = self.goals.get_goal_detail(goal_id)
        if not detail:
            return None
        _, versions = detail
        return next((v for v in versions if v.id == goal_version_id), None)

    def log_progress(
        self,
        owner: int,
        goal_id: int,
        amount: float,
        on: date | None = None,
        unit: str | None = None,
    ) -> dict:
        """Accrue progress toward an accumulation goal's chapter target
        (mcp-tools §3.1). The plan item's status DERIVES from the logged
        progress — there is no separate log_outcome for accumulation goals."""
        on = on or date.today()
        detail = self.goals.get_goal_detail(goal_id)
        if not detail:
            raise ValueError(f"no goal {goal_id}")
        _, versions = detail
        version = next(
            (
                v
                for v in versions
                if v.recurrence_type == RecurrenceType.ACCUMULATION
                and v.effective_to is None
            ),
            None,
        )
        if version is None:
            raise ValueError(
                f"goal {goal_id} has no active accumulation version; "
                "log_progress applies only to accumulation goals"
            )

        plan = self.plans.get_or_create_plan(owner, on)
        item = self.plans.get_or_create_item(plan.id, goal_id, version.id)
        item = self.plans.accrue_progress(item.id, amount)
        total = self.plans.sum_progress(goal_id)
        target = version.target_quantity
        return {
            "item": item.model_dump(),
            "total": total,
            "target": target,
            "unit": unit or version.quantity_unit,
            "reached": accumulation_reached(total, target),
        }

    def lock_in_plan(self, daily_plan_id: int, explicit: bool = True) -> dict:
        return self.plans.lock_in(daily_plan_id, explicit).model_dump()

    def add_win(self, owner: int, text: str, goal_id: int | None = None) -> dict:
        return self.wins.add_win(
            WinLogEntry(person_id=owner, text=text, source="manual", goal_id=goal_id)
        ).model_dump()

    def record_reflection(self, daily_plan_item_id: int, what_shifted: str) -> dict:
        self.plans.set_item_reflection(daily_plan_item_id, what_shifted)
        return {"ok": True}

    # --- reassessment lifecycle (B6, mcp-tools §3.2) ---
    # Every one of these fires ONLY from an explicit user choice in the
    # conversation. Nothing here is ever called automatically — the reassessment
    # nudge only *offers*; the human decides (non-negotiable 5, never auto-drop).

    def set_goal_lifecycle(self, goal_id: int, state: str) -> dict:
        """One verb-per-state surface hiding the two-table split: archive/
        unarchive write goal.archived_at; pause/activate write
        goal_version.lifecycle (dormant-not-dropped on-ramp)."""
        if state == "archive":
            self.goals.set_goal_archived(goal_id, datetime.now())
        elif state == "unarchive":
            self.goals.set_goal_archived(goal_id, None)
        elif state == "pause":
            self.goals.set_versions_lifecycle(goal_id, "active", "paused")
        elif state == "activate":
            self.goals.set_versions_lifecycle(goal_id, "paused", "active")
        else:
            raise ValueError(
                "set_goal_lifecycle state must be archive|unarchive|pause|activate"
            )
        return {"goal_id": goal_id, "state": state, "ok": True}

    def set_rotation_pointer(self, goal_id: int, position: int) -> dict:
        """Manually set a rotation goal's pointer ('today is a push-up day').
        No completion is attached and no other state is touched — this is never a
        side effect of log_outcome (mcp-tools §3.2)."""
        self.goals.set_rotation_pointer(goal_id, position)
        return {"goal_id": goal_id, "position": position, "ok": True}

    # --- rotation groups (ADR-0016) — authored structure, created at ingest ---

    def create_rotation_group(
        self, owner: int, name: str, sequence: list[dict]
    ) -> dict:
        """Create a cross-goal cadence group. `sequence` entries are
        {"goal_id": N} or {"rest": true}. Goal refs are validated here (the
        jsonb column carries no FK — app-enforced, ADR-0016): each member must
        exist, belong to `owner`, be unarchived, and not already be scheduled
        by another active group (the group is a member's SOLE scheduler)."""
        member_ids = []
        for entry in sequence:
            if entry == {"rest": True}:
                continue
            if set(entry) == {"goal_id"} and isinstance(entry["goal_id"], int):
                member_ids.append(entry["goal_id"])
                continue
            raise ValueError(
                'sequence entries must be {"goal_id": N} or {"rest": true}; '
                f"rejected: {entry!r}"
            )
        if not member_ids:
            raise ValueError("a rotation group needs at least one member goal")

        for gid in member_ids:
            detail = self.goals.get_goal_detail(gid)
            if detail is None:
                raise ValueError(f"no goal {gid}")
            goal = detail[0]
            if goal.owner_profile_id != owner:
                raise ValueError(f"goal {gid} does not belong to owner {owner}")
            if goal.archived_at is not None:
                raise ValueError(f"goal {gid} is archived")
            existing = self.goals.get_rotation_group_for_goal(gid)
            if existing is not None:
                raise ValueError(
                    f"goal {gid} is already scheduled by rotation group "
                    f"{existing.id} ({existing.name!r}); a goal has one scheduler"
                )

        group = self.goals.create_rotation_group(
            RotationGroup(owner_profile_id=owner, name=name, sequence=sequence)
        )
        return group.model_dump()

    def set_rotation_group_pointer(self, group_id: int, position: int) -> dict:
        """Manually set a group's pointer ('today is a push-up day'). Mirrors
        set_rotation_pointer — no completion attached, never a side effect."""
        self.goals.set_rotation_group_pointer(group_id, position)
        return {"group_id": group_id, "position": position, "ok": True}

    def archive_rotation_group(self, group_id: int) -> dict:
        """Archive a group (authoring edit, like removal-from-markdown — not a
        miss consequence). Members degrade gracefully back to self-scheduling
        on their own recurrence."""
        self.goals.set_rotation_group_archived(group_id, datetime.now())
        return {"group_id": group_id, "archived": True}

    def list_rotation_groups(self, owner: int) -> list[dict]:
        return [
            {**g.model_dump(), "member_goal_ids": rotation_group_member_ids(g.sequence)}
            for g in self.goals.list_rotation_groups(owner)
        ]

    # --- reads ---

    def get_full_goal_list(self, owner: int, on: date) -> list[dict]:
        return [g.model_dump() for g in self.goals.get_full_goal_list(owner, on)]

    def get_plan(self, owner: int, on: date) -> dict:
        plan = self.plans.get_or_create_plan(owner, on)
        items = self.plans.get_plan_items(plan.id)
        return {"plan": plan.model_dump(), "items": [i.model_dump() for i in items]}

    def get_goal_detail(self, goal_id: int) -> dict:
        result = self.goals.get_goal_detail(goal_id)
        if result is None:
            return {}
        goal, versions = result
        return {
            "goal": goal.model_dump(),
            "versions": [v.model_dump() for v in versions],
        }

    def get_active_chapter(self, owner: int, on: date) -> dict | None:
        ch = self.goals.get_active_chapter(owner, on)
        return ch.model_dump() if ch else None

    def get_miss_detail(self, goal_id: int) -> dict:
        """The engaged-miss count + day-by-day for one goal (name-the-bar gate,
        OQ-COMP-1). This is the ONLY source of the count; it is called ONLY after
        the user explicitly assents to look — never in the assemble path, never
        volunteered. Keyed to engaged (`not_done`) misses; silence never counts.
        Never comparative — one goal, never relative to the partner."""
        detail = self.goals.get_goal_detail(goal_id)
        title = detail[0].title if detail else None
        dates = self.plans.list_engaged_miss_dates(goal_id)
        return {
            "goal_id": goal_id,
            "goal_title": title,
            "engaged_miss_count": len(dates),
            "engaged_miss_dates": [str(d) for d in dates],
        }

    def get_goals_for_chapter(
        self, chapter_id: int, owner: int | None = None
    ) -> list[dict]:
        return [
            g.model_dump() for g in self.goals.get_goals_for_chapter(chapter_id, owner)
        ]

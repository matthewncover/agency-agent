from abc import ABC, abstractmethod
from datetime import date, datetime

from goal_bot.domain.entities import (
    Chapter,
    DailyPlan,
    DailyPlanItem,
    Goal,
    GoalState,
    GoalVersion,
    Insight,
    PlanItemStatus,
    RotationGroup,
    Visualization,
    WinLogEntry,
)


class GoalRepositoryPort(ABC):
    @abstractmethod
    def create_chapter(self, chapter: Chapter) -> Chapter: ...

    @abstractmethod
    def get_active_chapter(self, owner_profile_id: int, on: date) -> Chapter | None: ...

    @abstractmethod
    def get_latest_chapter_before(
        self, owner_profile_id: int, before: date
    ) -> Chapter | None:
        """The owner's most recent chapter that started before `before` — the
        rollover's archive target. Unlike get_active_chapter this tolerates a
        gap between chapters (a late rollover): chapters are not assumed
        contiguous."""

    @abstractmethod
    def get_chapter(self, chapter_id: int) -> Chapter | None: ...

    @abstractmethod
    def create_goal(self, goal: Goal) -> Goal: ...

    @abstractmethod
    def create_goal_version(self, version: GoalVersion) -> GoalVersion: ...

    @abstractmethod
    def create_goals_with_versions(
        self, goals: list[tuple[Goal, list[GoalVersion]]]
    ) -> list[tuple[Goal, list[GoalVersion]]]: ...

    @abstractmethod
    def create_goal_versions(
        self, versions: list[GoalVersion]
    ) -> list[GoalVersion]: ...

    @abstractmethod
    def get_goal_detail(
        self, goal_id: int
    ) -> tuple[Goal, list[GoalVersion]] | None: ...

    @abstractmethod
    def get_full_goal_list(self, owner_profile_id: int, on: date) -> list[Goal]: ...

    @abstractmethod
    def get_goals_for_chapter(
        self, chapter_id: int, owner_profile_id: int | None = None
    ) -> list[Goal]:
        """Goals scoped to a chapter (the re-ingest diff + rollover read).
        Optionally owner-scoped; includes archived goals so the diff can see
        what disappeared (§5.4)."""
        ...

    @abstractmethod
    def list_all_goals(self, owner_profile_id: int) -> list[Goal]:
        """Every goal the owner has, any chapter, archived or not — the
        past-goal pool for goal-setting candidate-gathering (§5.5)."""
        ...

    @abstractmethod
    def archive_chapter_goals(self, chapter_id: int) -> list[int]:
        """Archive (set archived_at) every not-yet-archived goal in a chapter,
        returning their ids. Used by rollover to close the prior chapter."""
        ...

    @abstractmethod
    def update_goal(self, goal_id: int, fields: dict) -> Goal | None: ...

    # --- carry-over counter (goal_state.carry_over_count) ---
    # Advanced ONLY on engaged `not_done` (ENGAGEMENT-NOT-FAILURE); reset on
    # `done`. Silence never reaches these — no tool call fires (NULL-TOLERANCE).

    @abstractmethod
    def advance_carry_over(self, goal_id: int) -> int:
        """Increment carry_over_count by 1, returning the new count."""
        ...

    @abstractmethod
    def reset_carry_over(self, goal_id: int) -> None:
        """Reset carry_over_count to 0 (a `done` halts the chain)."""
        ...

    @abstractmethod
    def get_carry_over_count(self, goal_id: int) -> int: ...

    # --- pointer state (goal_state.rotation_index / last_completed_at) ---
    # Advanced ONLY on engaged `done` (mcp-tools §3.1 completion side effects).

    @abstractmethod
    def get_goal_state(self, goal_id: int) -> GoalState: ...

    @abstractmethod
    def advance_rotation(self, goal_id: int, new_index: int, when: datetime) -> int:
        """Set the rotation pointer to `new_index` and stamp last_completed_at
        to `when`. `done` only — a miss holds the pointer so the item
        re-surfaces (spec §5). The caller computes new_index from the SURFACED
        slot via the domain walk (ADR-0016), never from the raw stored pointer."""
        ...

    @abstractmethod
    def set_last_completed(self, goal_id: int, when: datetime) -> None:
        """Stamp an interval goal's completion clock (resets its due window)."""
        ...

    # --- rotation groups (ADR-0016) — the cross-goal cadence scheduler ---
    # A group is NOT a goal: sequence of {"goal_id": N} | {"rest": true}
    # entries plus the shared pointer. Pointer advances ONLY on an engaged
    # `done` of the surfaced member; a miss holds it; silence touches nothing.

    @abstractmethod
    def create_rotation_group(self, group: RotationGroup) -> RotationGroup: ...

    @abstractmethod
    def get_rotation_group(self, group_id: int) -> RotationGroup | None: ...

    @abstractmethod
    def list_rotation_groups(self, owner_profile_id: int) -> list[RotationGroup]:
        """The owner's ACTIVE (non-archived) groups — the assemble-path read."""
        ...

    @abstractmethod
    def get_rotation_group_for_goal(self, goal_id: int) -> RotationGroup | None:
        """The active group whose sequence references the goal, if any — the
        sole-scheduler membership check (at most one, app-enforced at create)."""
        ...

    @abstractmethod
    def advance_rotation_group(
        self, group_id: int, new_index: int, when: datetime
    ) -> int:
        """Set the group pointer to `new_index` and stamp last_completed_at to
        `when` — the `done` side effect, computed from the surfaced entry."""
        ...

    @abstractmethod
    def set_rotation_group_pointer(self, group_id: int, position: int) -> None:
        """Manually set the group pointer — no completion attached (mirrors
        set_rotation_pointer, mcp-tools §3.2)."""
        ...

    @abstractmethod
    def set_rotation_group_archived(self, group_id: int, when: datetime | None) -> None:
        """Archive/unarchive a group. Members degrade gracefully back to their
        own recurrence when no active group schedules them."""
        ...

    # --- reassessment lifecycle (B6, mcp-tools §3.2). NEVER auto-fired: only an
    #     explicit user choice in the conversation reaches these (non-negotiable 5).

    @abstractmethod
    def set_goal_archived(self, goal_id: int, when: datetime | None) -> None:
        """Set/clear goal.archived_at (archive=now / unarchive=None)."""
        ...

    @abstractmethod
    def set_versions_lifecycle(
        self, goal_id: int, from_state: str, to_state: str
    ) -> int:
        """Flip the goal's versions' lifecycle (pause: active→paused;
        activate: paused→active). Returns rows changed."""
        ...

    @abstractmethod
    def set_rotation_pointer(self, goal_id: int, position: int) -> None:
        """Manually set the rotation pointer — no completion attached, never a
        side effect of any other tool (mcp-tools §3.2)."""
        ...

    # --- Tier-3 insight digest (goalbot.insight) ---

    @abstractmethod
    def list_active_insights(self, person_id: int) -> list[Insight]:
        """Active Tier-3 patterns for the person — surfaced as confirm/reject
        hypotheses (D-11), never as verdicts."""
        ...


class PlanRepositoryPort(ABC):
    @abstractmethod
    def get_or_create_plan(self, person_id: int, plan_date: date) -> DailyPlan: ...

    @abstractmethod
    def get_plan_items(self, daily_plan_id: int) -> list[DailyPlanItem]: ...

    @abstractmethod
    def get_item(self, item_id: int) -> DailyPlanItem | None: ...

    @abstractmethod
    def get_item_plan_date(self, item_id: int) -> date | None:
        """The plan_date the item belongs to — used to detect backdated logs
        (backdating pointer goals is restricted, mcp-tools §3.1/§5)."""
        ...

    @abstractmethod
    def add_plan_item(self, item: DailyPlanItem) -> DailyPlanItem: ...

    @abstractmethod
    def set_item_outcome(
        self,
        item_id: int,
        status: PlanItemStatus,
        quantity_actual: float | None = None,
    ) -> DailyPlanItem: ...

    @abstractmethod
    def set_item_reflection(self, item_id: int, what_shifted: str) -> None: ...

    @abstractmethod
    def lock_in(self, daily_plan_id: int, explicit: bool) -> DailyPlan: ...

    @abstractmethod
    def get_plan_for_date(
        self, person_id: int, plan_date: date
    ) -> tuple[DailyPlan, list[DailyPlanItem]] | None: ...

    @abstractmethod
    def mark_carried_over(self, item_ids: list[int]) -> None:
        """Transition rolled items to `carried_over` for presence-tracking.
        This is NOT a miss and never advances carry_over_count — it tracks
        presence-in-the-loop across days (mcp-tools §4.1)."""
        ...

    # --- quota budgeting + accumulation accrual (B4) ---

    @abstractmethod
    def count_done_in_window(self, goal_id: int, start: date, end: date) -> int:
        """Count `done` plan items for a goal across [start, end] — the session
        count a quota goal budgets against (spec §3, per-session binary)."""
        ...

    @abstractmethod
    def get_or_create_item(
        self, daily_plan_id: int, goal_id: int, goal_version_id: int
    ) -> DailyPlanItem:
        """Fetch the plan item for a goal on a plan, creating it if absent
        (accumulation goals log progress on days they may not be pre-planned)."""
        ...

    @abstractmethod
    def accrue_progress(self, item_id: int, amount: float) -> DailyPlanItem:
        """Add `amount` to an accumulation item's quantity_actual and derive its
        status to `done` — progress logged IS the completion (mcp-tools §3.1)."""
        ...

    @abstractmethod
    def sum_progress(self, goal_id: int) -> float:
        """Total logged progress for an accumulation goal (toward its chapter
        target). Sums quantity_actual across the goal's plan items."""
        ...

    @abstractmethod
    def list_engaged_miss_dates(self, goal_id: int) -> list[date]:
        """Dates the person self-reported `not_done` for a goal — the engaged
        (never silent) misses behind `get_miss_detail`. Surfaced ONLY on assent
        (name-the-bar gate, OQ-COMP-1); never in the assemble path."""
        ...


class WinRepositoryPort(ABC):
    @abstractmethod
    def add_win(self, win: WinLogEntry) -> WinLogEntry: ...

    @abstractmethod
    def list_wins(self, person_id: int, limit: int = 20) -> list[WinLogEntry]: ...


class VisualizationRepositoryPort(ABC):
    """Before-bed /visualize captures, reshared at the next morning fire."""

    @abstractmethod
    def add_visualization(self, person_id: int, text: str) -> Visualization: ...

    @abstractmethod
    def claim_unsurfaced(self, person_id: int, plan_date: date) -> list[Visualization]:
        """Every not-yet-surfaced capture for the person, oldest first, marked
        surfaced_on=plan_date in the same transaction. Consume-on-read: a claimed
        row never resurfaces (same-day re-fires included), so a visualization
        that doesn't pan out leaves no trail to be guilted over."""
        ...

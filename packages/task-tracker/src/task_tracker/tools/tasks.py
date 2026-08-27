from datetime import date

from task_tracker.application.use_cases import (
    BatchUpdateTasksUseCase,
    CompleteTaskUseCase,
    CreateTasksUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetOpenTasksUseCase,
    GetTaskDetailUseCase,
    GetTasksUpdatedOnUseCase,
    GetTrackerDataUseCase,
    NukeTaskUseCase,
    RestoreTaskUseCase,
    SearchTasksUseCase,
    UpdateTaskUseCase,
)


def register(mcp, repos, include: set[str] | None = None):
    """Register task tools on `mcp`. `include=None` registers everything; a set
    of tool names registers that subset (the shared surface's curated grant —
    see create_shared_app). Returns only the registered tools."""
    task_repo = repos["task"]
    daily_log_repo = repos["daily_log"]
    system_meta_repo = repos["system_meta"]

    def tool(description: str):
        def deco(fn):
            if include is None or fn.__name__ in include:
                return mcp.tool(description=description)(fn)
            return fn

        return deco

    # --- Task CRUD ---

    @tool(
        description=(
            "Create a single personal task. Use when Matthew mentions a new "
            "task, errand, or item to track. For multiple tasks at once (brain "
            "dumps, listing out errands), use create_tasks instead."
        )
    )
    def create_task(
        title: str,
        tier: int | None = None,
        status: str = "not_started",
        deadline: str | None = None,
        parent_task_id: int | None = None,
        is_commitment: bool = False,
        commitment_notes: str | None = None,
        priority_rank: int | None = None,
        pinned: bool = False,
        private: bool = False,
        notes: str | None = None,
    ) -> dict:
        """Create a single personal task.

        Args:
            title: Short task description
            tier: 1 (hard deadline/external), 2 (important, no external accountability), 3 (someday/maybe)
            status: Initial status. Defaults to 'not_started'.
            deadline: Hard deadline date if one exists (ISO format).
            parent_task_id: ID of parent task for subtasks. One level of nesting only.
            is_commitment: True when Matthew has made an explicit promise to someone (or himself, with a deadline)
            commitment_notes: Context for commitments: who, when, what was promised
            priority_rank: Relative ordering, scoped to tier. Rank 1 = highest within that tier.
            pinned: Tier 3 only. Pinned items appear in the 'what this is all for' motivational section of the tracker.
            private: Private tasks are invisible to goal-bot and to the shared task surface — use for anything that shouldn't surface outside this tracker (e.g. gifts, surprises).
            notes: Detailed context, history, or background. Not shown in list views.
        """
        fields = {"title": title, "status": status}
        if tier is not None:
            fields["tier"] = tier
        if pinned:
            fields["pinned"] = pinned
        if private:
            fields["private"] = private
        if is_commitment:
            fields["is_commitment"] = is_commitment
        if commitment_notes:
            fields["commitment_notes"] = commitment_notes
        if deadline:
            fields["deadline"] = date.fromisoformat(deadline)
        if parent_task_id is not None:
            fields["parent_task_id"] = parent_task_id
        if priority_rank is not None:
            fields["priority_rank"] = priority_rank
        if notes:
            fields["notes"] = notes

        uc = CreateTaskUseCase(task_repo)
        task = uc.execute(**fields)
        return task.model_dump(mode="json")

    @tool(
        description=(
            "Batch create multiple tasks at once. Use when Matthew drops "
            "several items at once — brain dumps or listing out errands. More "
            "efficient than multiple create_task calls."
        )
    )
    def create_tasks(tasks: list[dict]) -> list[dict]:
        """Batch create multiple tasks at once.

        Args:
            tasks: List of task objects. Each follows the same schema as create_task.
        """
        processed = []
        for task_data in tasks:
            task_data = dict(task_data)
            task_data.pop("type", None)  # tolerated legacy key (ADR-0019)
            if task_data.get("deadline"):
                task_data["deadline"] = date.fromisoformat(task_data["deadline"])
            processed.append(task_data)
        uc = CreateTasksUseCase(task_repo)
        results = uc.execute(processed)
        return [r.model_dump(mode="json") for r in results]

    @tool(
        description=(
            "Get full detail for a single task including rich notes and "
            "history. Children are returned inline with full detail. Use when "
            "Matthew says he's going to work on a specific task and needs "
            "context, or when reviewing a task's history."
        )
    )
    def get_task_detail(id: int) -> dict | None:
        """Get full detail for a single task.

        Args:
            id: Task ID
        """
        uc = GetTaskDetailUseCase(task_repo)
        task = uc.execute(id)
        if task is None:
            return None
        return task.model_dump(mode="json")

    @tool(
        description=(
            "Update one or more fields on a single task. Use for field changes "
            "like reprioritizing, updating notes, changing status, setting "
            "deadlines, or adding blocked_reason. For completing a task, prefer "
            "complete_task. For dropping a task, prefer nuke_task. For updating "
            "many tasks at once, use batch_update_tasks."
        )
    )
    def update_task(
        id: int,
        title: str | None = None,
        tier: int | None = None,
        status: str | None = None,
        blocked_reason: str | None = None,
        deadline: str | None = None,
        parent_task_id: int | None = None,
        is_commitment: bool | None = None,
        commitment_notes: str | None = None,
        priority_rank: int | None = None,
        pinned: bool | None = None,
        private: bool | None = None,
        notes: str | None = None,
    ) -> dict | None:
        """Update one or more fields on a single task.

        Args:
            id: Task ID
            title: Short task description. Editable, but titles are the handle used to match spoken references to records — avoid editing one into something vague.
            tier: 1, 2, or 3
            status: Task status
            blocked_reason: Why the task is blocked
            deadline: Hard deadline (ISO format)
            parent_task_id: Parent task ID for subtasks
            is_commitment: Whether an explicit promise was made
            commitment_notes: Context for commitments
            priority_rank: Relative ordering within the tier
            pinned: Tier 3 only
            private: True hides the task from goal-bot and the shared task surface; False re-exposes it.
            notes: Detailed context
        """
        fields = {}
        local_vars = {
            "title": title,
            "tier": tier,
            "status": status,
            "blocked_reason": blocked_reason,
            "parent_task_id": parent_task_id,
            "is_commitment": is_commitment,
            "commitment_notes": commitment_notes,
            "priority_rank": priority_rank,
            "pinned": pinned,
            "private": private,
            "notes": notes,
        }
        for k, v in local_vars.items():
            if v is not None:
                fields[k] = v
        if deadline is not None:
            fields["deadline"] = date.fromisoformat(deadline)

        uc = UpdateTaskUseCase(task_repo)
        task = uc.execute(id, **fields)
        if task is None:
            return None
        return task.model_dump(mode="json")

    @tool(
        description=(
            "Update multiple tasks in a single call. Use for EOD status sweeps "
            "(marking several tasks done/in_progress), tier reorganizations, or "
            "any situation where 3+ tasks change at once."
        )
    )
    def batch_update_tasks(updates: list[dict]) -> list[dict | None]:
        """Update multiple tasks in a single call.

        Args:
            updates: List of {id, ...fields} objects. Each follows the same field schema as update_task.
        """
        for u in updates:
            u.pop("type", None)  # tolerated legacy key (ADR-0019)
            if u.get("deadline"):
                u["deadline"] = date.fromisoformat(u["deadline"])
        uc = BatchUpdateTasksUseCase(task_repo)
        results = uc.execute(updates)
        return [r.model_dump(mode="json") if r else None for r in results]

    @tool(
        description=(
            "Mark a task as done. Sets status='done' and completed_at=now. Use "
            "when Matthew says a task is finished, done, completed, or "
            "resolved. This is the default for any positive completion — "
            "prefer this over update_task(status='done')."
        )
    )
    def complete_task(id: int) -> dict | None:
        """Mark a task as done.

        Args:
            id: Task ID
        """
        uc = CompleteTaskUseCase(task_repo)
        task = uc.execute(id)
        if task is None:
            return None
        return task.model_dump(mode="json")

    @tool(
        description=(
            "Mark a task as explicitly dropped — decided not to do. Sets "
            "status='nuked', preserves all data. Use when Matthew decides to "
            "abandon, drop, skip, or deprioritize indefinitely. Default choice "
            "when removing a task — only use delete_task if the task was a mistake "
            "or duplicate that shouldn't appear in any history."
        )
    )
    def nuke_task(id: int) -> dict | None:
        """Mark a task as explicitly dropped.

        Args:
            id: Task ID
        """
        uc = NukeTaskUseCase(task_repo)
        task = uc.execute(id)
        if task is None:
            return None
        return task.model_dump(mode="json")

    @tool(
        description=(
            "Soft delete a task (sets deleted_at). Filtered out of ALL "
            "queries. Use ONLY for confirmed mistakes or duplicates — tasks "
            "that should never have existed. For tasks Matthew chose not to "
            "do, use nuke_task instead (preserves visibility in history)."
        )
    )
    def delete_task(id: int) -> dict:
        """Soft delete a task.

        Args:
            id: Task ID
        """
        uc = DeleteTaskUseCase(task_repo)
        success = uc.execute(id)
        return {"deleted": success}

    @tool(
        description=(
            "Restore (undelete) a soft-deleted task by clearing its deleted_at. "
            "The reverse of delete_task — use when a task was deleted by mistake. "
            "Acts only if the task is currently soft-deleted; if it isn't deleted "
            "this is a no-op and simply returns the current record. Returns null "
            "if no task with that ID exists."
        )
    )
    def restore_task(id: int) -> dict | None:
        """Restore a soft-deleted task.

        Args:
            id: Task ID
        """
        uc = RestoreTaskUseCase(task_repo)
        task = uc.execute(id)
        if task is None:
            return None
        return task.model_dump(mode="json")

    # --- Task Queries ---

    @tool(
        description=(
            "Get all open (non-done, non-nuked, non-deleted) tasks. Returns "
            "lightweight fields without rich notes. Use for ad-hoc queries like "
            "'what items have I been carrying?' or 'show me all blocked "
            "tasks.' For daily tracker generation, prefer get_tracker_data "
            "which includes computed annotations. Use min_days_open=7 for the "
            "weekly item review (Mondays), min_days_open=30 for the monthly "
            "stale item review."
        )
    )
    def get_open_tasks(min_days_open: int | None = None) -> list[dict]:
        """Get all open tasks.

        Args:
            min_days_open: Only return tasks with days_carried >= this value. Useful for stale item reviews.
        """
        uc = GetOpenTasksUseCase(task_repo)
        return [t.model_dump(mode="json") for t in uc.execute(min_days_open)]

    @tool(
        description=(
            "Get tasks that had status changes or notes updated on a specific "
            "date. Returns flat list. Use as an optional cross-check when "
            "reviewing a day — catches tasks touched but not discussed in "
            "conversation."
        )
    )
    def get_tasks_updated_on(target_date: str) -> list[dict]:
        """Get tasks updated on a specific date.

        Args:
            target_date: Date to check (ISO format)
        """
        uc = GetTasksUpdatedOnUseCase(task_repo)
        return [
            t.model_dump(mode="json")
            for t in uc.execute(date.fromisoformat(target_date))
        ]

    @tool(
        description=(
            "Keyword-search tasks by title and notes. Returns lightweight ranked "
            "candidates (id, title, tier, status) — title matches rank above "
            "notes-only matches. This is a cheap keyword search, not semantic: it "
            "surfaces candidates for you to reason over, and will miss "
            "zero-token-overlap synonyms (e.g. 'bronco' won't match 'vehicle "
            "registration'). For those, search a synonym or fall back to "
            "get_open_tasks. Searches open tasks by default; set "
            "include_done/include_deleted to widen to completed or soft-deleted "
            "history."
        )
    )
    def search_tasks(
        query: str,
        include_done: bool = False,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """Keyword-search tasks by title and notes.

        Args:
            query: Keyword or phrase to match against title and notes.
            include_done: Include tasks with status 'done'. Default False.
            include_deleted: Include soft-deleted tasks. Default False.
            limit: Maximum number of results to return. Default 20.
        """
        uc = SearchTasksUseCase(task_repo)
        return uc.execute(query, include_done, include_deleted, limit)

    # --- Composite Queries ---

    @tool(
        description=(
            "Single call returning everything needed for daily tracker "
            "generation and morning kickoff. Returns: open personal tasks with "
            "computed annotations (is_stale, is_blocked, has_upcoming_deadline), "
            "today's daily log (whoop data, previous observations), and "
            "tier3_review_due flag. This is always the first call in a new "
            "day's session."
        )
    )
    def get_tracker_data() -> dict:
        """Single call returning everything needed for daily tracker generation."""
        uc = GetTrackerDataUseCase(task_repo, daily_log_repo, system_meta_repo)
        return uc.execute()

    tools = {
        "create_task": create_task,
        "create_tasks": create_tasks,
        "get_task_detail": get_task_detail,
        "update_task": update_task,
        "batch_update_tasks": batch_update_tasks,
        "complete_task": complete_task,
        "nuke_task": nuke_task,
        "delete_task": delete_task,
        "restore_task": restore_task,
        "get_open_tasks": get_open_tasks,
        "get_tasks_updated_on": get_tasks_updated_on,
        "search_tasks": search_tasks,
        "get_tracker_data": get_tracker_data,
    }
    if include is not None:
        tools = {name: fn for name, fn in tools.items() if name in include}
    return tools

from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_ritual_tools(mcp: FastMCP, uc: GoalUseCases) -> None:
    @mcp.tool
    def log_outcome(
        daily_plan_item_id: int, status: str, quantity_actual: float | None = None
    ) -> dict:
        """Record an outcome the user actively reported (done|partial|not_done)."""
        return uc.log_outcome(daily_plan_item_id, status, quantity_actual)

    @mcp.tool
    def revert_outcome(daily_plan_item_id: int) -> dict:
        """Undo a mis-logged outcome: restore the item to planned and clear
        quantity_actual. Does not rewind pointers or the carry-over counter."""
        return uc.revert_outcome(daily_plan_item_id)

    @mcp.tool
    def lock_in_plan(daily_plan_id: int, explicit: bool = True) -> dict:
        """Finalize a plan the user explicitly assented to."""
        return uc.lock_in_plan(daily_plan_id, explicit)

    @mcp.tool
    def add_win(owner: int, text: str, goal_id: int | None = None) -> dict:
        """Manual win entry, any time."""
        return uc.add_win(owner, text, goal_id)

    @mcp.tool
    def record_reflection(daily_plan_item_id: int, what_shifted: str) -> dict:
        """The 'what shifted' reflection (Tier-2)."""
        return uc.record_reflection(daily_plan_item_id, what_shifted)

    @mcp.tool
    def log_progress(
        owner: int,
        goal_id: int,
        amount: float,
        on: str | None = None,
        unit: str | None = None,
    ) -> dict:
        """Accrue progress toward an accumulation goal's chapter target. The
        plan item's status derives from the logged progress — never call
        log_outcome for an accumulation goal."""
        from datetime import date

        parsed = date.fromisoformat(on) if on else None
        return uc.log_progress(owner, goal_id, amount, on=parsed, unit=unit)

    # --- reassessment lifecycle (B6). Fire ONLY on an explicit user choice.
    @mcp.tool
    def set_goal_lifecycle(goal_id: int, state: str) -> dict:
        """Reassessment lifecycle action, chosen by the user: archive|unarchive
        (retire/redirect or one-off drop) · pause|activate (dormant-not-dropped).
        NEVER call this without an explicit choice in the conversation —
        the nudge only offers; the human decides (never auto-drop)."""
        return uc.set_goal_lifecycle(goal_id, state)

    @mcp.tool
    def set_rotation_pointer(goal_id: int, position: int) -> dict:
        """Manually set a rotation goal's pointer ('today is a push-up day').
        No completion attached; never a side effect of log_outcome."""
        return uc.set_rotation_pointer(goal_id, position)

    @mcp.tool
    def set_rotation_group_pointer(group_id: int, position: int) -> dict:
        """Manually set a rotation GROUP's pointer (ADR-0016 — 'today is a
        push-up day' when push-ups/pull-ups share one rhythm). No completion
        attached; never a side effect of log_outcome."""
        return uc.set_rotation_group_pointer(group_id, position)

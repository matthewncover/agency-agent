from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_ritual_tools(mcp: FastMCP, uc: GoalUseCases) -> None:
    @mcp.tool
    def log_outcome(daily_plan_item_id: int, status: str, quantity_actual: float | None = None) -> dict:
        """Record an outcome the user actively reported (done|partial|not_done)."""
        return uc.log_outcome(daily_plan_item_id, status, quantity_actual)

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

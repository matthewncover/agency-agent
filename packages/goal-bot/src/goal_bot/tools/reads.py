from datetime import date

from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_read_tools(mcp: FastMCP, uc: GoalUseCases) -> None:
    @mcp.tool
    def get_full_goal_list(owner: int, on: date) -> list[dict]:
        """All active goals for the owner on the given date."""
        return uc.get_full_goal_list(owner, on)

    @mcp.tool
    def get_plan(owner: int, on: date) -> dict:
        """Get (or create) the daily plan and its items for the given date."""
        return uc.get_plan(owner, on)

    @mcp.tool
    def get_goal_detail(goal_id: int) -> dict:
        """Fetch a goal and all its versions."""
        return uc.get_goal_detail(goal_id)

    @mcp.tool
    def get_active_chapter(owner: int, on: date) -> dict | None:
        """Return the chapter active on the given date, or None."""
        return uc.get_active_chapter(owner, on)

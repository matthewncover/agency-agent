from collections.abc import Iterable
from datetime import date

from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_read_tools(
    mcp: FastMCP, uc: GoalUseCases, *, include: Iterable[str] | None = None
) -> None:
    """Register read tools. `include` selects a subset by name (default: all) so
    a grant can omit reads it has no business holding — e.g. ingestion drops
    `get_plan`, which has a get-or-create side-effect and no ingestion use."""

    def get_full_goal_list(owner: int, on: date) -> list[dict]:
        """All active goals for the owner on the given date."""
        return uc.get_full_goal_list(owner, on)

    def get_plan(owner: int, on: date) -> dict:
        """Get (or create) the daily plan and its items for the given date."""
        return uc.get_plan(owner, on)

    def get_goal_detail(goal_id: int) -> dict:
        """Fetch a goal and all its versions."""
        return uc.get_goal_detail(goal_id)

    def get_active_chapter(owner: int, on: date) -> dict | None:
        """Return the chapter active on the given date, or None."""
        return uc.get_active_chapter(owner, on)

    available = {
        "get_full_goal_list": get_full_goal_list,
        "get_plan": get_plan,
        "get_goal_detail": get_goal_detail,
        "get_active_chapter": get_active_chapter,
    }
    names = list(available) if include is None else list(include)
    unknown = set(names) - set(available)
    if unknown:
        raise ValueError(f"unknown read tools: {sorted(unknown)}")
    for name in names:
        mcp.tool(available[name])

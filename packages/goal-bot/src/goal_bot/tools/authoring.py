from datetime import date

from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_authoring_tools(mcp: FastMCP, uc: GoalUseCases) -> None:
    @mcp.tool
    def create_chapter(owner: int, start: date, end: date, label: str | None = None) -> int:
        """Create a new chapter and return its id."""
        return uc.create_chapter(owner, start, end, label)

    @mcp.tool
    def create_goal(owner: int, title: str, chapter_id: int | None = None) -> int:
        """Create a new goal and return its id."""
        return uc.create_goal(owner, title, chapter_id)

    @mcp.tool
    def create_goal_version(
        goal_id: int,
        version_no: int,
        level: str,
        definition: str,
        recurrence_type: str,
        recurrence_config: dict,
        completion_type: str,
        why: str | None = None,
        target_quantity: float | None = None,
        quantity_unit: str | None = None,
        task_ref_source: str | None = None,
        task_ref_id: int | None = None,
        lifecycle: str = "active",
    ) -> int:
        """Create a new version for an existing goal and return the version id."""
        return uc.create_goal_version(
            goal_id=goal_id,
            version_no=version_no,
            level=level,
            definition=definition,
            why=why,
            recurrence_type=recurrence_type,
            recurrence_config=recurrence_config,
            completion_type=completion_type,
            target_quantity=target_quantity,
            quantity_unit=quantity_unit,
            task_ref_source=task_ref_source,
            task_ref_id=task_ref_id,
            lifecycle=lifecycle,
        )

    @mcp.tool
    def update_goal(goal_id: int, fields: dict) -> dict:
        """Update goal identity fields (title, tags, chapter_id, archived_at only)."""
        return uc.update_goal(goal_id, fields)

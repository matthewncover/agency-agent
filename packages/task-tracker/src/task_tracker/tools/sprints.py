from datetime import date

from task_tracker.application.use_cases import SetActiveSprintUseCase


def register(mcp, repos):
    sprint_repo = repos["sprint"]

    @mcp.tool(
        description=(
            "Create a new sprint and/or mark it as active, deactivating the "
            "previous sprint. Use at sprint boundaries (Tuesday EOD or Wednesday "
            "morning) to transition between sprints."
        )
    )
    def set_active_sprint(
        sprint_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Create a new sprint and/or mark it as active.

        Args:
            sprint_id: Sprint ID — use the end date as ID, e.g. '2026-03-17'
            start_date: Sprint start date (ISO format). Required when creating a new sprint.
            end_date: Sprint end date (ISO format). Required when creating a new sprint.
        """
        uc = SetActiveSprintUseCase(sprint_repo)
        sprint = uc.execute(
            sprint_id=sprint_id,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
        )
        return sprint.model_dump(mode="json")

    return {
        "set_active_sprint": set_active_sprint,
    }

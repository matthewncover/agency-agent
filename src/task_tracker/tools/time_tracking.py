from datetime import date

from task_tracker.application.use_cases import (
    DeleteTimeEntryUseCase,
    GetTimecardUseCase,
    GetTimeGapsUseCase,
    LogTimeUseCase,
)


def register(mcp, repos):
    time_entry_repo = repos["time_entry"]

    @mcp.tool(
        description=(
            "Log a time entry for a work task. Call when a time block in the "
            "tracker artifact is completed. Time blocks in the artifact are "
            "ephemeral planning; time_entries in the DB are the permanent record "
            "for timecards. JN bucket on the entry may differ from the task's "
            "default bucket."
        )
    )
    def log_time(
        work_task_id: int,
        target_date: str,
        duration_minutes: int,
        jn_bucket: str,
        notes: str | None = None,
    ) -> dict:
        """Log a time entry for a work task.

        Args:
            work_task_id: ID of the work task
            target_date: Date the work was done (ISO format)
            duration_minutes: Duration in minutes
            jn_bucket: Timecard category: 'planning', 'development', 'sustaining', 'overhead', 'training'. PR reviews default to 'development' unless the PR is for a bug/maintenance (then 'sustaining').
            notes: Optional. What happened during this block.
        """
        uc = LogTimeUseCase(time_entry_repo)
        entry = uc.execute(
            work_task_id=work_task_id,
            entry_date=date.fromisoformat(target_date),
            duration_minutes=duration_minutes,
            jn_bucket=jn_bucket,
            notes=notes,
        )
        return entry.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Hard-delete a time entry by its ID and return the removed row "
            "(date, bucket, minutes, work_task_id, notes) so the removal can be "
            "confirmed. Use to remove a mis-logged entry — e.g. time logged "
            "against the wrong task or in the wrong chat. Unlike tasks, a wrong "
            "time entry has no analytic value, so this is a permanent delete, not "
            "a soft delete. Returns null if no entry with that ID exists."
        )
    )
    def delete_time_entry(time_entry_id: int) -> dict | None:
        """Hard-delete a time entry and return the removed row.

        Args:
            time_entry_id: ID of the time entry to delete
        """
        uc = DeleteTimeEntryUseCase(time_entry_repo)
        entry = uc.execute(time_entry_id)
        if entry is None:
            return None
        return entry.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Get aggregated time data for timecard generation. Groups by date + "
            "jn_bucket, includes ODS ticket references. Use when Matthew asks for "
            "a timecard — pair with get_time_gaps to identify incomplete days."
        )
    )
    def get_timecard(start_date: str, end_date: str) -> list[dict]:
        """Get aggregated time data for timecard generation.

        Args:
            start_date: Start of range (ISO format)
            end_date: End of range (ISO format)
        """
        uc = GetTimecardUseCase(time_entry_repo)
        return uc.execute(
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )

    @mcp.tool(
        description=(
            "Compare logged time per day against ~8h expected. Flags days with "
            "incomplete logging. Use alongside get_timecard to identify where "
            "conversation context is needed to fill gaps, and to generate "
            "uncertainty notes in the timecard."
        )
    )
    def get_time_gaps(start_date: str, end_date: str) -> list[dict]:
        """Compare logged time per day against ~8h expected.

        Args:
            start_date: Start of range (ISO format)
            end_date: End of range (ISO format)
        """
        uc = GetTimeGapsUseCase(time_entry_repo)
        return uc.execute(
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )

    return {
        "log_time": log_time,
        "delete_time_entry": delete_time_entry,
        "get_timecard": get_timecard,
        "get_time_gaps": get_time_gaps,
    }

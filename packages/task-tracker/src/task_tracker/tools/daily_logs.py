from datetime import date

from task_tracker.application.use_cases import (
    GetDailyLogsUseCase,
    GetDailyLogUseCase,
    LogDailyUseCase,
    LogReflectionUseCase,
)


def register(mcp, repos):
    daily_log_repo = repos["daily_log"]

    @mcp.tool(
        description=(
            "Create or update a daily log entry. Use to record Whoop data when "
            "Matthew shares recovery scores, and for general day context notes. "
            "Creates the entry if it doesn't exist, updates if it does."
        )
    )
    def log_daily(
        target_date: str,
        whoop_recovery: int | None = None,
        whoop_hrv: int | None = None,
        whoop_sleep_hours: float | None = None,
        whoop_rhr: int | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create or update a daily log entry.

        Args:
            target_date: Date (ISO format)
            whoop_recovery: Recovery percentage (0-100)
            whoop_hrv: Heart rate variability
            whoop_sleep_hours: Hours of sleep
            whoop_rhr: Resting heart rate
            notes: General day context
        """
        uc = LogDailyUseCase(daily_log_repo)
        log = uc.execute(
            log_date=date.fromisoformat(target_date),
            whoop_recovery=whoop_recovery,
            whoop_hrv=whoop_hrv,
            whoop_sleep_hours=whoop_sleep_hours,
            whoop_rhr=whoop_rhr,
            notes=notes,
        )
        return log.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Set or update the structured EOD reflection for a date. All fields "
            "optional for partial updates. Matthew's answers go in the four "
            "reflection fields. Claude's pattern observations (streaks, "
            "correlations, trajectory notes) go in the observations field — kept "
            "separate from Matthew's self-assessment."
        )
    )
    def log_reflection(
        target_date: str,
        moved_forward: str | None = None,
        didnt_move: str | None = None,
        do_differently: str | None = None,
        protect_tomorrow: str | None = None,
        observations: str | None = None,
    ) -> dict | None:
        """Set or update structured EOD reflection.

        Args:
            target_date: Date (ISO format)
            moved_forward: What moved forward today — completions, partial progress, decisions, agency moments. Matthew's input.
            didnt_move: What didn't move and why — blockers vs. choices. Matthew's input.
            do_differently: What would I do differently — learning extraction. Matthew's input.
            protect_tomorrow: One thing to protect tomorrow — implementation intention. Matthew's input.
            observations: Claude's pattern observations — momentum streaks, whoop correlations, trajectory notes. Claude writes this, not Matthew.
        """
        fields = {}
        if moved_forward is not None:
            fields["moved_forward"] = moved_forward
        if didnt_move is not None:
            fields["didnt_move"] = didnt_move
        if do_differently is not None:
            fields["do_differently"] = do_differently
        if protect_tomorrow is not None:
            fields["protect_tomorrow"] = protect_tomorrow
        if observations is not None:
            fields["observations"] = observations

        uc = LogReflectionUseCase(daily_log_repo)
        log = uc.execute(date.fromisoformat(target_date), **fields)
        if log is None:
            return None
        return log.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Get a single day's log including whoop data, reflections, and "
            "observations. Use when reviewing a specific day's data."
        )
    )
    def get_daily_log(target_date: str) -> dict | None:
        """Get a single day's log.

        Args:
            target_date: Date (ISO format)
        """
        uc = GetDailyLogUseCase(daily_log_repo)
        log = uc.execute(date.fromisoformat(target_date))
        if log is None:
            return None
        return log.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Get daily logs across a date range. Use for pattern analysis — "
            "whoop-to-output correlation, distraction windows, estimation "
            "accuracy, reactive vs. proactive balance over time."
        )
    )
    def get_daily_logs(start_date: str, end_date: str) -> list[dict]:
        """Get daily logs across a date range.

        Args:
            start_date: Start of range (ISO format)
            end_date: End of range (ISO format)
        """
        uc = GetDailyLogsUseCase(daily_log_repo)
        logs = uc.execute(
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )
        return [log.model_dump(mode="json") for log in logs]

    return {
        "log_daily": log_daily,
        "log_reflection": log_reflection,
        "get_daily_log": get_daily_log,
        "get_daily_logs": get_daily_logs,
    }

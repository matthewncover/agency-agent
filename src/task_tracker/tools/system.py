import datetime
import zoneinfo

from task_tracker.application.use_cases import SetMetaUseCase

DEFAULT_TIMEZONE = "America/Los_Angeles"


def register(mcp, repos):
    system_meta_repo = repos["system_meta"]

    @mcp.tool(
        description=(
            "Write a system-level metadata value. Currently used for: "
            "'last_tier3_review' (date string) — set after completing a quarterly "
            "Tier 3 reflection so get_tracker_data can compute tier3_review_due. "
            "Read is handled server-side, not via a separate tool."
        )
    )
    def set_meta(key: str, value: str) -> dict:
        """Write a system-level metadata value.

        Args:
            key: Metadata key, e.g. 'last_tier3_review'
            value: Value as text string
        """
        uc = SetMetaUseCase(system_meta_repo)
        meta = uc.execute(key, value)
        return meta.model_dump(mode="json")

    @mcp.tool(
        description=(
            "Get the current date and time. Use at the start of any session to "
            "orient on today's date, day of week, and timezone. Essential for "
            "date-sensitive operations like sprint boundaries, deadlines, and "
            "daily log entries."
        )
    )
    def get_time(timezone: str | None = None) -> dict:
        """Get the current date and time.

        Args:
            timezone: Optional IANA timezone string (e.g. America/New_York, UTC).
                      Defaults to America/Los_Angeles (PT) when omitted.
        """
        tz_name = timezone or DEFAULT_TIMEZONE
        tz = zoneinfo.ZoneInfo(tz_name)
        now = datetime.datetime.now(tz)
        return {
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timezone": tz_name,
            "utc_offset": now.strftime("%z"),
        }

    return {
        "set_meta": set_meta,
        "get_time": get_time,
    }

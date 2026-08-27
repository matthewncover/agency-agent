import datetime
import zoneinfo

from task_tracker.application.use_cases import SetMetaUseCase

DEFAULT_TIMEZONE = "America/Los_Angeles"


def register(mcp, repos, engine=None, owner_id=None):
    system_meta_repo = repos["system_meta"]

    if engine is not None:

        @mcp.tool(
            description=(
                "Which database this server is bound to — fixed at LAUNCH; "
                ".env edits do NOT apply until the server is reconnected. Call "
                "first in any session that must not write to the wrong DB "
                "(dev vs prod) and show the user the answer. Never returns "
                "the password."
            )
        )
        def get_db_target() -> dict:
            """Report the server's bound database (sanitized) and owner id."""
            url = engine.url
            if url.database and url.database.endswith("_test"):
                looks_like = "test"
            elif url.port == 5433:
                looks_like = "prod (ssh tunnel :5433)"
            elif url.port in (None, 5432):
                looks_like = "dev (local :5432)"
            else:
                looks_like = "unknown"
            return {
                "host": url.host,
                "port": url.port,
                "database": url.database,
                "user": url.username,
                "owner_id": owner_id,
                "looks_like": looks_like,
            }

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
            "date-sensitive operations like deadlines and daily log entries."
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

    tools = {
        "set_meta": set_meta,
        "get_time": get_time,
    }
    if engine is not None:
        tools["get_db_target"] = get_db_target
    return tools

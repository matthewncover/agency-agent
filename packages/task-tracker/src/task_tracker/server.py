from fastmcp import FastMCP
from sqlalchemy import Engine

from task_tracker.infrastructure.adapters import (
    PgDailyLogRepositoryAdapter,
    PgSprintRepositoryAdapter,
    PgSystemMetaRepositoryAdapter,
    PgTaskRepositoryAdapter,
    PgTimeEntryRepositoryAdapter,
)
from task_tracker.infrastructure.engine import default_engine, default_owner_id
from task_tracker.tools import register_all


def create_app(engine: Engine | None = None, owner_id: int | None = None):
    """Build the MCP app with all tools registered against Postgres (ADR-0008).

    Args:
        engine: SQLAlchemy Engine for the shared Postgres. Defaults to one built
            from DATABASE_URL.
        owner_id: person the tools act for. Defaults to the env-resolved owner.

    Returns:
        Tuple of (mcp instance, dict of tool functions).
    """
    if engine is None:
        engine = default_engine()
    if owner_id is None:
        owner_id = default_owner_id()

    app = FastMCP("Task Tracker")
    repos = {
        "task": PgTaskRepositoryAdapter(engine, owner_id),
        "time_entry": PgTimeEntryRepositoryAdapter(engine),
        "sprint": PgSprintRepositoryAdapter(engine),
        "daily_log": PgDailyLogRepositoryAdapter(engine, owner_id),
        "system_meta": PgSystemMetaRepositoryAdapter(engine),
    }
    tools = register_all(app, repos)
    return app, tools


mcp, _tools = create_app()

# Expose tool functions at module level for direct access
globals().update(_tools)

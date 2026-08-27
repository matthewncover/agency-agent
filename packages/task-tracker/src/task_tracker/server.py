from fastmcp import FastMCP
from sqlalchemy import Engine

from task_tracker.infrastructure.adapters import (
    PgDailyLogRepositoryAdapter,
    PgSystemMetaRepositoryAdapter,
    PgTaskRepositoryAdapter,
)
from task_tracker.infrastructure.engine import default_engine, default_owner_id
from task_tracker.tools import register_all
from task_tracker.tools.tasks import register as register_tasks

# The shared surface's curated grant (ADR-0018): task reads only — no writes,
# no daily-log/meta tools, and get_tracker_data stays personal (it carries
# daily-log reflections).
SHARED_TOOLS = {
    "get_task_detail",
    "get_open_tasks",
    "search_tasks",
    "get_tasks_updated_on",
}


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
        "daily_log": PgDailyLogRepositoryAdapter(engine, owner_id),
        "system_meta": PgSystemMetaRepositoryAdapter(engine),
    }
    tools = register_all(app, repos)
    return app, tools


def create_shared_app(engine: Engine | None = None, owner_id: int | None = None):
    """Build the shared-facing MCP app (ADR-0018): read-only task tools backed
    by a repository that hides private tasks at the SQL layer.

    Mount THIS server (not create_app's) in any bot other people can talk to —
    e.g. the group chat goal-bot lives in. Privacy is enforced by which server
    a bot is pointed at, never by prompts or client-side tool filtering.

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

    app = FastMCP("Task Tracker (shared)")
    repos = {
        "task": PgTaskRepositoryAdapter(engine, owner_id, include_private=False),
        "daily_log": PgDailyLogRepositoryAdapter(engine, owner_id),
        "system_meta": PgSystemMetaRepositoryAdapter(engine),
    }
    tools = register_tasks(app, repos, include=SHARED_TOOLS)
    return app, tools


mcp, _tools = create_app()

# Expose tool functions at module level for direct access
globals().update(_tools)

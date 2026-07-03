from fastmcp import FastMCP

from task_tracker.infrastructure.adapters import (
    SqliteDailyLogRepositoryAdapter,
    SqliteSprintRepositoryAdapter,
    SqliteSystemMetaRepositoryAdapter,
    SqliteTaskRepositoryAdapter,
    SqliteTimeEntryRepositoryAdapter,
)
from task_tracker.infrastructure.database import (
    ConnectionFactory,
    get_connection,
    init_db,
)
from task_tracker.tools import register_all


def create_app(conn_factory=None):
    """Build the MCP app with all tools registered.

    Args:
        conn_factory: Callable returning a sqlite3.Connection. If None,
            uses the default file-based DB with a ConnectionFactory.

    Returns:
        Tuple of (mcp instance, dict of tool functions).
    """
    if conn_factory is None:
        conn = get_connection()
        init_db(conn)
        conn.close()
        conn_factory = ConnectionFactory()

    app = FastMCP("Task Tracker")
    repos = {
        "task": SqliteTaskRepositoryAdapter(conn_factory),
        "time_entry": SqliteTimeEntryRepositoryAdapter(conn_factory),
        "sprint": SqliteSprintRepositoryAdapter(conn_factory),
        "daily_log": SqliteDailyLogRepositoryAdapter(conn_factory),
        "system_meta": SqliteSystemMetaRepositoryAdapter(conn_factory),
    }
    tools = register_all(app, repos)
    return app, tools


mcp, _tools = create_app()

# Expose tool functions at module level for direct access
globals().update(_tools)

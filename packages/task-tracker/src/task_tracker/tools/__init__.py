from task_tracker.tools.daily_logs import register as register_daily_logs
from task_tracker.tools.system import register as register_system
from task_tracker.tools.tasks import register as register_tasks


def register_all(mcp, repos, engine=None, owner_id=None):
    """Register all tools on the MCP instance. Returns dict of tool functions."""
    tools = {}
    tools.update(register_tasks(mcp, repos))
    tools.update(register_daily_logs(mcp, repos))
    tools.update(register_system(mcp, repos, engine=engine, owner_id=owner_id))
    return tools

import sys

# `python -m task_tracker` runs the full personal server; `--shared` runs the
# read-only surface that hides private tasks (ADR-0018). Which flag a bot's MCP
# config uses IS the privacy boundary — see create_shared_app.
if "--shared" in sys.argv[1:]:
    from task_tracker.server import create_shared_app

    shared_mcp, _ = create_shared_app()
    shared_mcp.run()
else:
    from task_tracker.server import mcp

    mcp.run()

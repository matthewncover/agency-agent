# Task Tracker MCP Server

Personal productivity MCP server exposing task and time tracking tools
for a Claude Project. SQLite-backed, clean architecture, Python.

## Spec

`docs/spec.md` is the source of truth — schema, tools, architecture,
naming conventions, and tool descriptions. Read it before making
architectural or design decisions.

## Commands

pytest                    # run tests
python -m task_tracker    # run server (local stdio)
ruff check .              # lint
ruff format .             # format

## Testing

Write and run tests during development. Cover entity validation,
use case logic (especially computed fields like days_carried and
actual_hours), repository CRUD against test SQLite, and tool-level
integration.

## Style

PEP 8 enforced by ruff. The linter is authoritative.
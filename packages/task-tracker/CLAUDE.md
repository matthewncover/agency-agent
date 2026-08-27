# Task Tracker MCP Server

Personal productivity MCP server exposing personal task and daily-log
tracking tools for a Claude Project (personal-only — no work tasks,
sprints, or time tracking; ADR-0019). Postgres, clean architecture,
Python.

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
use case logic (especially computed fields like days_carried),
repository CRUD against the test Postgres, and tool-level
integration.

## Style

PEP 8 enforced by ruff. The linter is authoritative.
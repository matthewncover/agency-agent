import asyncio
from datetime import date

import pytest
from goal_bot.server import (
    INGESTION_TOOLS,
    RITUAL_TOOLS,
    build_ingestion_server,
    build_server,
)

TODAY = date(2026, 6, 27)


def _tool_names(server) -> set[str]:
    async def _list():
        from fastmcp import Client

        async with Client(server) as c:
            return {t.name for t in await c.list_tools()}

    return asyncio.run(_list())


@pytest.fixture
def server(migrated_engine):
    return build_server(migrated_engine)


def test_server_exposes_all_named_tools(server):
    names = _tool_names(server)
    for name in RITUAL_TOOLS + INGESTION_TOOLS:
        assert name in names, f"expected tool {name!r} not found in server"


def test_ingestion_grant_is_exactly_its_tools(migrated_engine):
    names = _tool_names(build_ingestion_server(migrated_engine))
    assert names == set(INGESTION_TOOLS)


def test_ingestion_grant_excludes_get_plan_and_ritual_writes(migrated_engine):
    names = _tool_names(build_ingestion_server(migrated_engine))
    # get_plan has a get-or-create side-effect; ritual writes are out of grant.
    for forbidden in ("get_plan", "log_outcome", "lock_in_plan", "add_win"):
        assert forbidden not in names


@pytest.mark.integration
def test_add_win_via_tool(server, person_id):
    async def _call():
        from fastmcp import Client

        async with Client(server) as c:
            return await c.call_tool("add_win", {"owner": person_id, "text": "smoke"})

    result = asyncio.run(_call())
    assert result is not None

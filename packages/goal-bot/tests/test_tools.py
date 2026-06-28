import asyncio
from datetime import date

import pytest
from goal_bot.server import INGESTION_TOOLS, RITUAL_TOOLS, build_server

TODAY = date(2026, 6, 27)


@pytest.fixture
def server(migrated_engine):
    return build_server(migrated_engine)


def test_server_exposes_all_named_tools(server):
    async def _list():
        from fastmcp import Client
        async with Client(server) as c:
            return {t.name for t in await c.list_tools()}

    names = asyncio.run(_list())
    for name in RITUAL_TOOLS + INGESTION_TOOLS:
        assert name in names, f"expected tool {name!r} not found in server"


@pytest.mark.integration
def test_add_win_via_tool(server, person_id):
    async def _call():
        from fastmcp import Client
        async with Client(server) as c:
            return await c.call_tool("add_win", {"owner": person_id, "text": "smoke"})

    result = asyncio.run(_call())
    assert result is not None

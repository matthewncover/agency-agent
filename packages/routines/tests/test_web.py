"""The HTTP API end to end through aiohttp's test client (needs Postgres)."""

import asyncio
import json
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer
from routines.application.checklist_service import ChecklistService
from routines.infrastructure.telegram_auth import sign_init_data
from routines.web.server import Authenticator, build_web_app

pytestmark = pytest.mark.integration

TOKEN = "123456:test-token"
TG_USER = 8682973380


def tma(user_id: int) -> str:
    fields = {
        "auth_date": "9999999999",  # far future: never stale in tests
        "user": json.dumps({"id": user_id}),
    }
    fields["hash"] = sign_init_data(fields, TOKEN)
    return "tma " + urlencode(fields)


def run_with_client(service, person_id, scenario, dev=False):
    sent: list[str] = []

    async def notify(text):
        sent.append(text)

    auth = Authenticator(TOKEN, {TG_USER: person_id}, person_id if dev else None)

    async def main():
        async with TestClient(TestServer(build_web_app(service, auth, notify))) as c:
            await scenario(c, sent)

    asyncio.run(main())
    return sent


@pytest.fixture
def service(repo, profiles, person_id):
    return ChecklistService(repo, profiles, {person_id: "his"})


def test_full_flow(service, person_id):
    headers = {"Authorization": tma(TG_USER)}

    async def scenario(c, sent):
        r = await c.get("/api/list", headers=headers)
        assert r.status == 200
        assert await r.json() == {"name": "Matthew", "sent_today": False, "items": []}

        r = await c.put(
            "/api/list",
            headers=headers,
            json={
                "items": [
                    {"id": None, "text": "Stretch"},
                    {
                        "id": None,
                        "text": "Hygiene",
                        "children": [{"id": None, "text": "Teeth"}],
                    },
                ]
            },
        )
        body = await r.json()
        stretch, hygiene = body["items"]
        assert hygiene["children"][0]["text"] == "Teeth"

        r = await c.post(
            "/api/check", headers=headers, json={"id": stretch["id"], "checked": True}
        )
        r = await c.post(
            "/api/check",
            headers=headers,
            json={"id": hygiene["children"][0]["id"], "checked": True},
        )
        body = await r.json()
        assert body["items"][1]["checked"] is True  # derived from its child

        r = await c.post("/api/send", headers=headers, json={"note": "nice"})
        assert r.status == 200 and (await r.json())["sent_today"] is True
        assert sent == [
            'Matthew completed his morning routine! Stretch, Hygiene\n\n"nice"'
        ]

        r = await c.post("/api/send", headers=headers, json={"note": None})
        assert r.status == 409
        assert len(sent) == 1

    run_with_client(service, person_id, scenario)


def test_auth_failures(service, person_id):
    async def scenario(c, sent):
        assert (await c.get("/api/list")).status == 401
        bad = {"Authorization": tma(TG_USER).replace("hash=", "hash=0")}
        assert (await c.get("/api/list", headers=bad)).status == 401
        stranger = {"Authorization": tma(12345)}
        r = await c.get("/api/list", headers=stranger)
        assert r.status == 403 and (await r.json()) == {"error": "not set up"}

    run_with_client(service, person_id, scenario)


def test_bad_requests_are_400s(service, person_id):
    async def scenario(c, sent):
        h = {"Authorization": tma(TG_USER)}
        assert (await c.put("/api/list", headers=h, data="nope")).status == 400
        assert (await c.put("/api/list", headers=h, json={"items": "x"})).status == 400
        r = await c.put(
            "/api/list", headers=h, json={"items": [{"id": None, "text": ""}]}
        )
        assert r.status == 400 and "error" in await r.json()
        assert (await c.post("/api/check", headers=h, json={"id": "1"})).status == 400
        assert (
            await c.post("/api/check", headers=h, json={"id": 1, "checked": True})
        ).status == 404
        assert (await c.post("/api/send", headers=h, json={})).status == 400

    run_with_client(service, person_id, scenario)


def test_failed_post_frees_the_send(service, person_id):
    async def scenario(c, sent):
        h = {"Authorization": tma(TG_USER)}
        r = await c.put(
            "/api/list", headers=h, json={"items": [{"id": None, "text": "Stretch"}]}
        )
        item_id = (await r.json())["items"][0]["id"]
        await c.post("/api/check", headers=h, json={"id": item_id, "checked": True})
        r = await c.post("/api/send", headers=h, json={})
        assert r.status == 502
        assert (await (await c.get("/api/list", headers=h)).json())[
            "sent_today"
        ] is False

    async def failing_notify(text):
        raise RuntimeError("telegram down")

    auth = Authenticator(TOKEN, {TG_USER: person_id})

    async def main():
        app = build_web_app(service, auth, failing_notify)
        async with TestClient(TestServer(app)) as c:
            await scenario(c, [])

    asyncio.run(main())


def test_dev_mode_skips_auth_and_serves_the_page(service, person_id):
    async def scenario(c, sent):
        assert (await c.get("/api/list")).status == 200
        r = await c.get("/")
        assert r.status == 200 and "<title>" in await r.text()

    run_with_client(service, person_id, scenario, dev=True)

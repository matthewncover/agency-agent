"""The Mini App page and its JSON API (ADR-0021).

Caddy strips the `/morning` prefix, so routes sit at the root and the page
uses relative URLs. Every /api/ request carries `Authorization: tma
<initData>`; the auth middleware turns it into a person id. DB work is
synchronous (SQLAlchemy + psycopg), so it runs off the event loop the bot
shares.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from aiohttp import web

from routines.application.checklist_service import (
    AlreadySentError,
    ChecklistService,
    ChecklistView,
    NothingDoneError,
    StaleListError,
    UnknownItemError,
    UnknownPersonError,
)
from routines.domain.checklist import Item, ListError
from routines.infrastructure.telegram_auth import InitDataError, verify_init_data

_log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
PERSON_KEY = web.RequestKey("person_id", int)

Notifier = Callable[[str], Awaitable[None]]


class UnauthorizedError(Exception):
    """The request isn't from a verified Telegram user."""


class NotSetUpError(Exception):
    """A verified Telegram user who isn't mapped to a person."""


class Authenticator:
    """initData -> person id. With a dev person id, every request is that
    person (the config refuses this unless bound to loopback)."""

    def __init__(
        self,
        bot_token: str,
        user_person: dict[int, int],
        dev_person_id: int | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._user_person = user_person
        self._dev_person_id = dev_person_id

    def person_for(self, authorization: str) -> int:
        if self._dev_person_id:
            return self._dev_person_id
        scheme, _, init_data = authorization.partition(" ")
        if scheme.lower() != "tma":
            raise UnauthorizedError
        try:
            user_id = verify_init_data(init_data, self._bot_token)
        except InitDataError as exc:
            raise UnauthorizedError from exc
        person_id = self._user_person.get(user_id)
        if person_id is None:
            _log.info("mini app opened by unmapped telegram user %s", user_id)
            raise NotSetUpError
        return person_id


def _error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _item_json(item: Item) -> dict:
    return {
        "id": item.id,
        "text": item.text,
        "checked": item.done,
        "children": [_item_json(c) for c in item.children],
    }


def _view_json(view: ChecklistView) -> web.Response:
    return web.json_response(
        {
            "name": view.name,
            "sent_today": view.sent_today,
            "items": [_item_json(i) for i in view.items],
        }
    )


def _parse_items(raw: object) -> list[Item]:
    if not isinstance(raw, list):
        raise ListError("items must be a list")
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ListError("each item must be an object")
        item_id, text = entry.get("id"), entry.get("text")
        if item_id is not None and type(item_id) is not int:
            raise ListError("item ids must be integers")
        if not isinstance(text, str):
            raise ListError("item text must be a string")
        children = _parse_items(entry.get("children") or [])
        items.append(Item(id=item_id, text=text, children=children))
    return items


async def _json_body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except ValueError as exc:
        raise ListError("body must be JSON") from exc
    if not isinstance(body, dict):
        raise ListError("body must be a JSON object")
    return body


def build_web_app(
    service: ChecklistService,
    auth: Authenticator,
    notify: Notifier,
) -> web.Application:
    @web.middleware
    async def guard(request: web.Request, handler):
        if not request.path.startswith("/api/"):
            return await handler(request)
        try:
            request[PERSON_KEY] = auth.person_for(
                request.headers.get("Authorization", "")
            )
            return await handler(request)
        except UnauthorizedError:
            return _error(401, "unauthorized")
        except (NotSetUpError, UnknownPersonError):
            return _error(403, "not set up")
        except ListError as exc:
            return _error(400, str(exc))

    async def index(request: web.Request) -> web.StreamResponse:
        return web.FileResponse(
            STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
        )

    async def get_list(request: web.Request) -> web.Response:
        view = await asyncio.to_thread(service.view, request[PERSON_KEY])
        return _view_json(view)

    async def post_check(request: web.Request) -> web.Response:
        body = await _json_body(request)
        item_id, checked = body.get("id"), body.get("checked")
        if type(item_id) is not int or not isinstance(checked, bool):
            raise ListError("expected {id: int, checked: bool}")
        try:
            view = await asyncio.to_thread(
                service.check, request[PERSON_KEY], item_id, checked
            )
        except UnknownItemError:
            return _error(404, "no such item; reload")
        return _view_json(view)

    async def put_list(request: web.Request) -> web.Response:
        body = await _json_body(request)
        items = _parse_items(body.get("items"))
        try:
            view = await asyncio.to_thread(service.replace, request[PERSON_KEY], items)
        except StaleListError:
            return _error(409, "list changed elsewhere")
        return _view_json(view)

    async def post_send(request: web.Request) -> web.Response:
        person_id = request[PERSON_KEY]
        body = await _json_body(request)
        note = body.get("note")
        if note is not None and not isinstance(note, str):
            raise ListError("note must be a string")
        try:
            message, today = await asyncio.to_thread(
                service.claim_send, person_id, note
            )
        except AlreadySentError:
            return _error(409, "already sent today")
        except NothingDoneError:
            return _error(400, "nothing finished yet")
        try:
            await notify(message)
        except Exception:
            _log.exception("completion message failed to send")
            await asyncio.to_thread(service.release_send, person_id, today)
            return _error(502, "couldn't post to Telegram; try again")
        view = await asyncio.to_thread(service.view, person_id)
        return _view_json(view)

    app = web.Application(middlewares=[guard])
    app.router.add_get("/", index)
    app.router.add_get("/api/list", get_list)
    app.router.add_post("/api/check", post_check)
    app.router.add_put("/api/list", put_list)
    app.router.add_post("/api/send", post_send)
    return app

"""Telegram Mini App identity (ADR-0021).

Telegram hands the page a signed `initData` query string. The server checks
its HMAC against the bot token, so the user id inside can be trusted without
any login or secret in the URL. See
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 24 * 60 * 60


class InitDataError(ValueError):
    """initData is missing, malformed, forged, or too old."""


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """The hash Telegram would attach to `fields` (all fields except `hash`)."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age: int = MAX_AGE_SECONDS,
    now: float | None = None,
) -> int:
    """Return the Telegram user id from a genuine, recent initData string."""
    if not init_data or not bot_token:
        raise InitDataError("no initData")
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InitDataError("malformed initData") from exc

    received = fields.pop("hash", "")
    if not hmac.compare_digest(received, sign_init_data(fields, bot_token)):
        raise InitDataError("bad signature")

    try:
        auth_date = int(fields["auth_date"])
        user_id = int(json.loads(fields["user"])["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InitDataError("initData lacks a user") from exc

    current = time.time() if now is None else now
    if current - auth_date > max_age:
        raise InitDataError("initData expired")
    return user_id

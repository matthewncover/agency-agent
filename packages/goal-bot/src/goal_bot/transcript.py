"""Debug transcript channel: one JSON line per chat message / tool call, on a
dedicated logger under the goal_bot INFO namespace. On the VPS journald picks
these up via the service's stderr; the chat-logs skill reads them back with
journalctl. Message text is private user content — this exists for debugging
and pattern review, nothing downstream consumes it."""

import json
import logging
from datetime import UTC, datetime

_log = logging.getLogger("goal_bot.transcript")


def _emit(payload: dict) -> None:
    payload["ts"] = datetime.now(UTC).isoformat(timespec="seconds")
    _log.info(json.dumps(payload, ensure_ascii=False, default=str))


def log_message(chat_id: int, person_id: int, direction: str, text: str) -> None:
    """direction: "in" (user → bot) or "out" (bot → user)."""
    _emit(
        {
            "chat_id": chat_id,
            "person_id": person_id,
            "direction": direction,
            "text": text,
        }
    )


def log_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
) -> None:
    """One line per API call (a turn with tool calls = several calls)."""
    _emit(
        {
            "direction": "usage",
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
        }
    )


def log_tool(name: str, args: dict, result: dict) -> None:
    """Tool call + outcome. Correlate with messages by timestamp."""
    error = result.get("error") if isinstance(result, dict) else None
    _emit(
        {
            "direction": "tool",
            "tool": name,
            "args": args,
            "ok": error is None,
            "error": error,
        }
    )

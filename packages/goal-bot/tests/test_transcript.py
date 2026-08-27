import json
import logging

from goal_bot import transcript


def _last_json(caplog) -> dict:
    line = caplog.records[-1].getMessage()
    assert "\n" not in line  # journald/grep contract: one line per event
    return json.loads(line)


def test_log_message_emits_single_line_json(caplog):
    with caplog.at_level(logging.INFO, logger="goal_bot.transcript"):
        transcript.log_message(11, 1, "in", "line one\nline two")
    payload = _last_json(caplog)
    assert payload["chat_id"] == 11
    assert payload["person_id"] == 1
    assert payload["direction"] == "in"
    assert payload["text"] == "line one\nline two"
    assert payload["ts"]


def test_log_tool_carries_ok_and_error(caplog):
    with caplog.at_level(logging.INFO, logger="goal_bot.transcript"):
        transcript.log_tool("log_outcome", {"daily_plan_item_id": 3}, {"error": "boom"})
    payload = _last_json(caplog)
    assert payload["direction"] == "tool"
    assert payload["tool"] == "log_outcome"
    assert payload["ok"] is False
    assert payload["error"] == "boom"


def test_log_usage_fields(caplog):
    with caplog.at_level(logging.INFO, logger="goal_bot.transcript"):
        transcript.log_usage(
            "claude-sonnet-5",
            input_tokens=5000,
            output_tokens=300,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
    payload = _last_json(caplog)
    assert payload["direction"] == "usage"
    assert payload["model"] == "claude-sonnet-5"
    assert payload["input_tokens"] == 5000
    assert payload["output_tokens"] == 300
    assert payload["cache_read_input_tokens"] == 0

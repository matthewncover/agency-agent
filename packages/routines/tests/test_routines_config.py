from datetime import time

import pytest
from routines.config import Settings


def settings(**kw):
    base = {
        "routines_bot_token": "t",
        "routines_bot_username": "a_bot",
        "routines_chat_id": -100,
    }
    return Settings(_env_file=None, **(base | kw))


def test_maps_and_link_parse():
    s = settings(
        telegram_user_map="111:1, 222:2",
        routines_possessive="1:his,2:her",
        routines_morning_time="06:30",
    )
    assert s.user_person() == {111: 1, 222: 2}
    assert s.possessive() == {1: "his", 2: "her"}
    assert s.morning_time() == time(6, 30)
    assert s.miniapp_link() == "https://t.me/a_bot/morning"
    s.check()


def test_dev_bypass_refuses_public_bind():
    with pytest.raises(SystemExit):
        settings(routines_dev_person_id=1, routines_http_host="0.0.0.0").check()
    settings(routines_dev_person_id=1).check()


def test_bot_needs_username_and_chat():
    with pytest.raises(SystemExit):
        settings(routines_chat_id=0).check()


def test_no_token_only_allowed_in_dev():
    with pytest.raises(SystemExit):
        settings(routines_bot_token="").check()
    settings(routines_bot_token="", routines_dev_person_id=1).check()

import json
from urllib.parse import urlencode

import pytest
from routines.infrastructure.telegram_auth import (
    InitDataError,
    sign_init_data,
    verify_init_data,
)

TOKEN = "123456:test-token"
NOW = 1_800_000_000


def init_data(user_id=42, auth_date=NOW, token=TOKEN, **overrides):
    fields = {
        "auth_date": str(auth_date),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "M"}),
    }
    fields["hash"] = sign_init_data(fields, token)
    fields.update(overrides)
    return urlencode(fields)


def test_valid_init_data_returns_the_user_id():
    assert verify_init_data(init_data(), TOKEN, now=NOW + 60) == 42


def test_tampered_user_is_rejected():
    tampered = init_data(user=json.dumps({"id": 7, "first_name": "M"}))
    with pytest.raises(InitDataError):
        verify_init_data(tampered, TOKEN, now=NOW)


def test_signed_with_another_token_is_rejected():
    with pytest.raises(InitDataError):
        verify_init_data(init_data(token="999:other"), TOKEN, now=NOW)


def test_stale_init_data_is_rejected():
    with pytest.raises(InitDataError):
        verify_init_data(init_data(), TOKEN, now=NOW + 24 * 3600 + 1)


@pytest.mark.parametrize("raw", ["", "not a query", "hash=abc"])
def test_garbage_is_rejected(raw):
    with pytest.raises(InitDataError):
        verify_init_data(raw, TOKEN, now=NOW)


def test_missing_user_is_rejected():
    fields = {"auth_date": str(NOW)}
    fields["hash"] = sign_init_data(fields, TOKEN)
    with pytest.raises(InitDataError):
        verify_init_data(urlencode(fields), TOKEN, now=NOW)

"""ADR-0017 — liveness heartbeat / dead-man's switch.

The heartbeat watches the *system's* promise ("I will show up every morning"),
never the user's behavior: it fires on successful scheduled delivery, stays
silent when the send fails, and is completely blind to whether the user
replies. The pinger sits behind HeartbeatPort so tests fake it; the no-op
adapter keeps dev/tests free of any external watchdog."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from goal_bot.application.heartbeat_port import HeartbeatPort, NoopHeartbeat
from goal_bot.composition import build_heartbeat
from goal_bot.config import Settings
from goal_bot.infrastructure.heartbeat import HttpHeartbeat
from goal_bot.infrastructure.telegram_adapter import TelegramAdapter

_TOKEN = "123456:ABCdefGHIjklMNOpqrs"


class FakeHeartbeat(HeartbeatPort):
    def __init__(self) -> None:
        self.pings = 0

    async def ping(self) -> None:
        self.pings += 1


class _FakeService:
    """Stands in for MorningService: fire_morning returns a session whose
    response_text is what would be sent."""

    def __init__(self, text: str = "Good morning — win first.") -> None:
        self._text = text

    def fire_morning(self, person_id, day):
        return SimpleNamespace(ctx=None, messages=[], response_text=self._text)


class _FakeBot:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[int, str]] = []
        self._fail = fail

    async def send_message(self, chat_id, text) -> None:
        if self._fail:
            raise RuntimeError("telegram send path down")
        self.sent.append((chat_id, text))


def _adapter(service, heartbeat, bot):
    from agency_profile.domain.entities import Person

    a = TelegramAdapter(
        token=_TOKEN,
        chat_person={111: 1},
        persons={1: Person(display_name="A", timezone="America/Los_Angeles")},
        service=service,
        scheduler=None,
        heartbeat=heartbeat,
    )
    a._app = SimpleNamespace(bot=bot)  # swap PTB out from under the job
    return a


# --- the send-path hook -------------------------------------------------------


def test_heartbeat_fires_on_successful_scheduled_send():
    hb, bot = FakeHeartbeat(), _FakeBot()
    job = _adapter(_FakeService(), hb, bot).morning_job_for(1)
    asyncio.run(job())
    assert len(bot.sent) == 1
    assert hb.pings == 1


def test_user_silence_is_still_a_healthy_heartbeat():
    # Send happened, user never replied → still exactly one healthy ping.
    # The heartbeat keys on delivery, never on engagement (NULL-TOLERANCE
    # stays about the user; this is about us).
    hb, bot = FakeHeartbeat(), _FakeBot()
    adapter = _adapter(_FakeService(), hb, bot)
    asyncio.run(adapter.morning_job_for(1)())
    # ... a whole day of silence passes: no replies handled, nothing else runs
    assert hb.pings == 1


def test_no_ping_when_send_fails():
    hb = FakeHeartbeat()
    job = _adapter(_FakeService(), hb, _FakeBot(fail=True)).morning_job_for(1)
    with pytest.raises(RuntimeError):
        asyncio.run(job())
    assert hb.pings == 0


def test_no_ping_when_nothing_was_sent():
    # No message text ⇒ nothing delivered ⇒ no heartbeat. "Delivered" means
    # delivered — an empty morning must look dead to the watchdog.
    hb, bot = FakeHeartbeat(), _FakeBot()
    job = _adapter(_FakeService(text=""), hb, bot).morning_job_for(1)
    asyncio.run(job())
    assert bot.sent == []
    assert hb.pings == 0


def test_adapter_defaults_to_noop_heartbeat():
    bot = _FakeBot()
    from agency_profile.domain.entities import Person

    a = TelegramAdapter(
        token=_TOKEN,
        chat_person={111: 1},
        persons={1: Person(display_name="A", timezone="America/Los_Angeles")},
        service=_FakeService(),
        scheduler=None,
    )
    a._app = SimpleNamespace(bot=bot)
    asyncio.run(a.morning_job_for(1)())  # must not raise without a heartbeat
    assert len(bot.sent) == 1


# --- adapters -----------------------------------------------------------------


def test_noop_heartbeat_is_safe():
    asyncio.run(NoopHeartbeat().ping())


def test_http_heartbeat_pings_the_configured_url():
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        return httpx.Response(200)

    hb = HttpHeartbeat(
        "https://hc.example/ping/abc", transport=httpx.MockTransport(handler)
    )
    asyncio.run(hb.ping())
    assert hits == ["https://hc.example/ping/abc"]


def test_http_heartbeat_swallows_transport_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("watchdog unreachable")

    hb = HttpHeartbeat(
        "https://hc.example/ping/abc", transport=httpx.MockTransport(handler)
    )
    asyncio.run(hb.ping())  # must not raise — the send it monitors comes first


def test_http_heartbeat_swallows_http_errors():
    hb = HttpHeartbeat(
        "https://hc.example/ping/abc",
        transport=httpx.MockTransport(lambda req: httpx.Response(500)),
    )
    asyncio.run(hb.ping())


# --- composition --------------------------------------------------------------


def test_build_heartbeat_unconfigured_is_noop():
    assert isinstance(build_heartbeat(Settings(heartbeat_url="")), NoopHeartbeat)


def test_build_heartbeat_configured_is_http():
    hb = build_heartbeat(Settings(heartbeat_url="https://hc.example/ping/abc"))
    assert isinstance(hb, HttpHeartbeat)

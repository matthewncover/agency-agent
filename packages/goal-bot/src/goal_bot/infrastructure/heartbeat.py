import logging

import httpx

from goal_bot.application.heartbeat_port import HeartbeatPort

_log = logging.getLogger(__name__)


class HttpHeartbeat(HeartbeatPort):
    """Pings an external dead-man's-switch URL (e.g. a healthchecks.io check)
    after each successful scheduled morning send (ADR-0017). The external
    watchdog alerts when an expected ping goes missing.

    Failures are logged and swallowed, never raised — a broken watchdog must
    not break the morning send it monitors."""

    def __init__(
        self,
        url: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._transport = transport  # injection point for tests

    async def ping(self) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
        except Exception:
            _log.warning("heartbeat ping failed (url=%s)", self._url, exc_info=True)

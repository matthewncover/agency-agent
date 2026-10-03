import logging

import httpx

from routines.application.ports import HeartbeatPort

_log = logging.getLogger(__name__)


class HttpHeartbeat(HeartbeatPort):
    """Pings the external dead-man's-switch URL after each scheduled morning
    send (ADR-0017). Kept as a small copy of goal-bot's pinger so this package
    doesn't depend on goal-bot. Failures are logged and swallowed: a broken
    watchdog must not break the send it monitors."""

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
            _log.warning("heartbeat ping failed", exc_info=True)

from abc import ABC, abstractmethod


class HeartbeatPort(ABC):
    """Liveness signal for the system's own promise to show up (ADR-0017).

    Pinged after a successful *scheduled* morning delivery — success means the
    message was actually sent. It never keys on whether the user responded:
    NULL-TOLERANCE keeps user silence neutral, and this port watches the bot,
    not the person. An answered morning and an ignored morning are equally
    healthy heartbeats.
    """

    @abstractmethod
    async def ping(self) -> None: ...


class NoopHeartbeat(HeartbeatPort):
    """The unconfigured default: dev and tests need no external watchdog."""

    async def ping(self) -> None:
        return None

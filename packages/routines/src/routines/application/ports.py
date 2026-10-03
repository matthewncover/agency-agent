from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from routines.domain.checklist import Item


@dataclass
class StoredChecklist:
    """A person's checklist as stored, before the lazy day reset is applied."""

    items: list[Item]
    state_date: date | None  # the day the stored `checked` flags belong to
    sent_date: date | None  # the day "Complete morning" last sent


class ChecklistRepositoryPort(ABC):
    @abstractmethod
    def load(self, person_id: int) -> StoredChecklist: ...

    @abstractmethod
    def set_checked(
        self, person_id: int, item_id: int, checked: bool, today: date
    ) -> bool:
        """Tick or untick a leaf for `today`, first clearing ticks left over
        from an earlier day. False when the item isn't this person's leaf."""

    @abstractmethod
    def replace_list(self, person_id: int, items: list[Item]) -> None:
        """Make the stored list exactly `items`, in order. Items with an id
        keep it (and their tick); items without one are created; stored items
        missing from `items` are deleted."""

    @abstractmethod
    def claim_send(self, person_id: int, today: date) -> bool:
        """Mark today as sent. False when it was already sent today."""

    @abstractmethod
    def release_send(self, person_id: int, today: date) -> None:
        """Undo today's claim (the message failed to go out)."""


class HeartbeatPort(ABC):
    @abstractmethod
    async def ping(self) -> None: ...


class NoopHeartbeat(HeartbeatPort):
    async def ping(self) -> None:
        return None

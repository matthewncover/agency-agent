from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from agency_profile.application.ports import ProfileRepositoryPort
from agency_profile.domain.entities import Person

from routines.application.ports import ChecklistRepositoryPort
from routines.domain.checklist import (
    MAX_NOTE,
    Item,
    ListError,
    checklist_day,
    done_texts,
    format_completion,
    validate_list,
)


class UnknownPersonError(LookupError):
    """The person id has no profile.person row."""


class UnknownItemError(LookupError):
    """The item isn't one of this person's checkable (leaf) items."""


class StaleListError(RuntimeError):
    """The submitted list names items that are no longer stored (edited
    elsewhere). The page should reload and let the person redo the edit."""


class AlreadySentError(RuntimeError):
    """Today's "Complete morning" message already went out."""


class NothingDoneError(RuntimeError):
    """No top-level item is done, so there's nothing to list."""


@dataclass
class ChecklistView:
    name: str
    items: list[Item]
    sent_today: bool


def _unchecked(items: list[Item]) -> list[Item]:
    return [
        Item(id=i.id, text=i.text, checked=False, children=_unchecked(i.children))
        for i in items
    ]


class ChecklistService:
    """Today's view of a person's checklist and the edits made to it. The
    reset is lazy: ticks stored for an earlier day read as unchecked."""

    def __init__(
        self,
        repo: ChecklistRepositoryPort,
        profiles: ProfileRepositoryPort,
        possessive: dict[int, str],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._profiles = profiles
        self._possessive = possessive
        self._clock = clock

    def _person(self, person_id: int) -> Person:
        person = self._profiles.get_person(person_id)
        if person is None:
            raise UnknownPersonError(person_id)
        return person

    def _today(self, person: Person) -> date:
        return checklist_day(self._clock(), person.timezone)

    def _view(self, person_id: int, person: Person) -> ChecklistView:
        today = self._today(person)
        stored = self._repo.load(person_id)
        items = stored.items if stored.state_date == today else _unchecked(stored.items)
        return ChecklistView(
            name=person.display_name,
            items=items,
            sent_today=stored.sent_date == today,
        )

    def view(self, person_id: int) -> ChecklistView:
        return self._view(person_id, self._person(person_id))

    def check(self, person_id: int, item_id: int, checked: bool) -> ChecklistView:
        person = self._person(person_id)
        if not self._repo.set_checked(person_id, item_id, checked, self._today(person)):
            raise UnknownItemError(item_id)
        return self._view(person_id, person)

    def replace(self, person_id: int, items: list[Item]) -> ChecklistView:
        person = self._person(person_id)
        stored_ids = {i.id for i in _flatten(self._repo.load(person_id).items)}
        cleaned = validate_list(items)
        if any(i.id not in stored_ids for i in _flatten(cleaned) if i.id is not None):
            raise StaleListError
        self._repo.replace_list(person_id, cleaned)
        return self._view(person_id, person)

    def claim_send(self, person_id: int, note: str | None) -> tuple[str, date]:
        """Reserve today's send and return the message to post. Call
        release_send if posting fails, so the button works again."""
        person = self._person(person_id)
        view = self._view(person_id, person)
        if view.sent_today:
            raise AlreadySentError
        if not done_texts(view.items):
            raise NothingDoneError
        if note is not None and len(note) > MAX_NOTE:
            raise ListError(f"notes are limited to {MAX_NOTE} characters")
        today = self._today(person)
        if not self._repo.claim_send(person_id, today):
            raise AlreadySentError
        possessive = self._possessive.get(person_id, "their")
        message = format_completion(person.display_name, possessive, view.items, note)
        return message, today

    def release_send(self, person_id: int, today: date) -> None:
        self._repo.release_send(person_id, today)


def _flatten(items: list[Item]) -> list[Item]:
    return [x for i in items for x in (i, *i.children)]

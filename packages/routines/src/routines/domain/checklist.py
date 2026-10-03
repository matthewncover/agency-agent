"""The morning checklist, as pure data and rules (no I/O).

A person's checklist is an ordered list of items with one level of
sub-items. A parent's state is derived: it's done only when every child is.
Ticks belong to a single checklist day, which starts at 03:00 local time, so
a late-night tick still counts toward that morning and the list resets before
the next one.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

RESET_HOUR = 3
MAX_TEXT = 200
MAX_NOTE = 1000
MAX_ITEMS = 100  # top-level + children; a guard, not a product limit


class ListError(ValueError):
    """A submitted list breaks a shape rule (depth, text length, size)."""


@dataclass
class Item:
    id: int | None
    text: str
    checked: bool = False
    children: list["Item"] = field(default_factory=list)

    @property
    def done(self) -> bool:
        if self.children:
            return all(c.checked for c in self.children)
        return self.checked


def checklist_day(now: datetime, tz: str) -> date:
    """The checklist day `now` (timezone-aware) falls in, for a person in `tz`."""
    local = now.astimezone(ZoneInfo(tz))
    return (local - timedelta(hours=RESET_HOUR)).date()


def validate_list(items: list[Item]) -> list[Item]:
    """Normalize (strip text) and check a submitted list. Raises ListError."""
    seen: set[int] = set()
    count = 0

    def clean(item: Item, depth: int) -> Item:
        nonlocal count
        count += 1
        text = item.text.strip()
        if not text:
            raise ListError("items need some text")
        if len(text) > MAX_TEXT:
            raise ListError(f"items are limited to {MAX_TEXT} characters")
        if item.id is not None:
            if item.id in seen:
                raise ListError("an item appears twice")
            seen.add(item.id)
        if depth > 0 and item.children:
            raise ListError("sub-items can't have sub-items")
        children = [clean(c, depth + 1) for c in item.children]
        return Item(id=item.id, text=text, children=children)

    cleaned = [clean(i, 0) for i in items]
    if count > MAX_ITEMS:
        raise ListError(f"a checklist is limited to {MAX_ITEMS} items")
    return cleaned


def all_done(items: list[Item]) -> bool:
    return bool(items) and all(i.done for i in items)


def done_texts(items: list[Item]) -> list[str]:
    """Top-level items that are done, in order. Sub-items are never listed."""
    return [i.text for i in items if i.done]


def format_completion(
    name: str, possessive: str, items: list[Item], note: str | None
) -> str:
    """The "Complete morning" message. Full wording when every item is done,
    otherwise the plain "{name}'s morning:" form. No counts, no times."""
    listed = ", ".join(done_texts(items))
    if all_done(items):
        message = f"{name} completed {possessive} morning routine! {listed}"
    else:
        message = f"{name}'s morning: {listed}"
    note = (note or "").strip()
    if note:
        message += f'\n\n"{note}"'
    return message

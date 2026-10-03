from datetime import UTC, date, datetime

import pytest
from routines.domain.checklist import (
    MAX_TEXT,
    Item,
    ListError,
    checklist_day,
    format_completion,
    validate_list,
)

LA = "America/Los_Angeles"


def leaf(text, checked=False, id=None):
    return Item(id=id, text=text, checked=checked)


def parent(text, *children, id=None):
    return Item(id=id, text=text, children=list(children))


# --- checklist_day: the day starts at 03:00 local ---


def test_before_three_am_belongs_to_the_previous_day():
    # 02:59 PDT on Oct 3 = 09:59 UTC
    assert checklist_day(datetime(2026, 10, 3, 9, 59, tzinfo=UTC), LA) == date(
        2026, 10, 2
    )


def test_three_am_starts_the_new_day():
    assert checklist_day(datetime(2026, 10, 3, 10, 0, tzinfo=UTC), LA) == date(
        2026, 10, 3
    )


def test_day_follows_the_persons_timezone():
    now = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)
    assert checklist_day(now, "Europe/Berlin") == date(2026, 10, 3)
    assert checklist_day(now, "Pacific/Honolulu") == date(2026, 10, 2)


# --- derived parents ---


def test_parent_is_done_only_when_every_child_is():
    p = parent("Hygiene", leaf("Teeth", True), leaf("Floss"))
    assert not p.done
    p.children[1].checked = True
    assert p.done


def test_a_parents_own_flag_is_ignored():
    p = parent("Hygiene", leaf("Teeth"))
    p.checked = True
    assert not p.done


# --- format_completion ---


def test_full_completion_uses_the_possessive_and_lists_top_level_items():
    items = [leaf("Stretch", True), parent("Hygiene", leaf("Teeth", True))]
    assert (
        format_completion("Matthew", "his", items, None)
        == "Matthew completed his morning routine! Stretch, Hygiene"
    )


def test_partial_lists_only_finished_top_level_items():
    items = [
        leaf("Stretch", True),
        parent("Hygiene", leaf("Teeth", True), leaf("Floss")),
        leaf("Journal"),
    ]
    assert format_completion("Jade", "her", items, None) == "Jade's morning: Stretch"


def test_note_is_quoted_after_a_blank_line():
    items = [leaf("Stretch", True)]
    assert (
        format_completion("Jade", "her", items, "  slept great ")
        == 'Jade completed her morning routine! Stretch\n\n"slept great"'
    )


def test_blank_note_is_dropped():
    items = [leaf("Stretch", True)]
    assert "\n" not in format_completion("Jade", "her", items, "   ")


# --- validate_list ---


def test_validate_strips_text():
    assert validate_list([leaf("  Stretch ")])[0].text == "Stretch"


@pytest.mark.parametrize(
    "items",
    [
        [leaf("   ")],
        [leaf("x" * (MAX_TEXT + 1))],
        [parent("a", parent("b", leaf("c")))],
        [leaf("a", id=1), leaf("b", id=1)],
        [leaf(str(n)) for n in range(101)],
    ],
    ids=["blank", "too-long", "grandchild", "duplicate-id", "too-many"],
)
def test_validate_rejects(items):
    with pytest.raises(ListError):
        validate_list(items)

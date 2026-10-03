"""ChecklistService against the real repository (needs Postgres)."""

from datetime import UTC, datetime, timedelta

import pytest
from routines.application.checklist_service import (
    AlreadySentError,
    ChecklistService,
    NothingDoneError,
    StaleListError,
    UnknownItemError,
)
from routines.domain.checklist import Item

pytestmark = pytest.mark.integration

# 08:00 PDT on Oct 3
MORNING = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock(MORNING)


@pytest.fixture
def service(repo, profiles, person_id, clock):
    return ChecklistService(repo, profiles, {person_id: "his"}, clock=clock)


def build(service, person_id):
    """Stretch, Hygiene[Teeth, Floss], Journal; returns the saved view."""
    return service.replace(
        person_id,
        [
            Item(id=None, text="Stretch"),
            Item(
                id=None,
                text="Hygiene",
                children=[Item(id=None, text="Teeth"), Item(id=None, text="Floss")],
            ),
            Item(id=None, text="Journal"),
        ],
    )


def ids(view):
    return {i.text: i.id for i in view.items} | {
        c.text: c.id for i in view.items for c in i.children
    }


def test_replace_creates_the_list_in_order(service, person_id):
    view = build(service, person_id)
    assert [i.text for i in view.items] == ["Stretch", "Hygiene", "Journal"]
    assert [c.text for c in view.items[1].children] == ["Teeth", "Floss"]
    assert view.name == "Matthew"
    assert not view.sent_today


def test_reorder_and_rename_keep_ids_and_ticks(service, person_id):
    view = build(service, person_id)
    n = ids(view)
    service.check(person_id, n["Stretch"], True)
    service.check(person_id, n["Teeth"], True)

    view = service.replace(
        person_id,
        [
            Item(id=n["Journal"], text="Journal"),
            Item(id=n["Stretch"], text="Stretch longer"),
            Item(
                id=n["Hygiene"],
                text="Hygiene",
                children=[Item(id=n["Teeth"], text="Teeth")],
            ),
        ],
    )
    assert [i.text for i in view.items] == ["Journal", "Stretch longer", "Hygiene"]
    assert view.items[1].checked and view.items[1].id == n["Stretch"]
    assert view.items[2].done  # Floss deleted, Teeth was ticked
    assert all(c.text != "Floss" for i in view.items for c in i.children)


def test_child_can_move_to_the_top_level(service, person_id):
    n = ids(build(service, person_id))
    view = service.replace(
        person_id,
        [
            Item(id=n["Hygiene"], text="Hygiene"),
            Item(id=n["Floss"], text="Floss"),
        ],
    )
    assert [i.text for i in view.items] == ["Hygiene", "Floss"]
    assert view.items[1].id == n["Floss"]


def test_unknown_ids_are_rejected(service, person_id):
    build(service, person_id)
    with pytest.raises(StaleListError):
        service.replace(person_id, [Item(id=999_999, text="ghost")])


def test_parents_cant_be_ticked(service, person_id):
    n = ids(build(service, person_id))
    with pytest.raises(UnknownItemError):
        service.check(person_id, n["Hygiene"], True)


def test_ticks_reset_at_three_am(service, person_id, clock):
    n = ids(build(service, person_id))
    service.check(person_id, n["Stretch"], True)
    assert service.view(person_id).items[0].checked

    clock.now = MORNING + timedelta(hours=18)  # 02:00 next day: still today
    assert service.view(person_id).items[0].checked

    clock.now = MORNING + timedelta(hours=19)  # 03:00 next day
    assert not service.view(person_id).items[0].checked

    # The first tick of the new day clears yesterday's leftovers for good.
    view = service.check(person_id, n["Journal"], True)
    assert not view.items[0].checked and view.items[2].checked


def test_send_once_per_day(service, person_id, clock):
    n = ids(build(service, person_id))
    with pytest.raises(NothingDoneError):
        service.claim_send(person_id, None)

    service.check(person_id, n["Teeth"], True)  # a sub-item alone lists nothing
    with pytest.raises(NothingDoneError):
        service.claim_send(person_id, None)

    service.check(person_id, n["Stretch"], True)
    message, _ = service.claim_send(person_id, "good one")
    assert message == 'Matthew\'s morning: Stretch\n\n"good one"'
    assert service.view(person_id).sent_today
    with pytest.raises(AlreadySentError):
        service.claim_send(person_id, None)

    clock.now = MORNING + timedelta(days=1)
    service.check(person_id, n["Stretch"], True)
    assert service.claim_send(person_id, None)[0] == "Matthew's morning: Stretch"


def test_full_completion_message(service, person_id):
    n = ids(build(service, person_id))
    for name in ("Stretch", "Teeth", "Floss", "Journal"):
        service.check(person_id, n[name], True)
    message, _ = service.claim_send(person_id, None)
    assert message == "Matthew completed his morning routine! Stretch, Hygiene, Journal"


def test_release_lets_a_failed_send_retry(service, person_id):
    n = ids(build(service, person_id))
    service.check(person_id, n["Stretch"], True)
    _, today = service.claim_send(person_id, None)
    service.release_send(person_id, today)
    assert not service.view(person_id).sent_today
    service.claim_send(person_id, None)


def test_lists_are_private(service, profiles, person_id):
    from agency_profile.domain.entities import Person

    jade = profiles.create_person(
        Person(display_name="Jade", timezone="America/Los_Angeles")
    )
    n = ids(build(service, person_id))
    assert service.view(jade.profile_id).items == []
    with pytest.raises(UnknownItemError):
        service.check(jade.profile_id, n["Stretch"], True)
    with pytest.raises(StaleListError):
        service.replace(jade.profile_id, [Item(id=n["Stretch"], text="mine now")])

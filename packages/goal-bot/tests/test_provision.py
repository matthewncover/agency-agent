from datetime import time

import pytest
from agency_profile.domain.entities import ProfileKind
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from goal_bot.provision import (
    _parse_members,
    _parse_morning,
    add_group,
    add_person,
)


def test_parse_morning():
    assert _parse_morning("07:30") == time(7, 30)


def test_parse_members():
    assert _parse_members("1, 2 ,3") == [1, 2, 3]


def test_parse_members_rejects_empty():
    with pytest.raises(ValueError):
        _parse_members(" , ")


@pytest.mark.integration
def test_add_person_creates_person(migrated_engine):
    repo = SqlAlchemyProfileRepository(migrated_engine)
    person = add_person(repo, name="Ada", timezone="America/New_York")
    assert person.profile_id is not None
    assert repo.get_kind(person.profile_id) == ProfileKind.PERSON
    fetched = repo.get_person(person.profile_id)
    assert fetched.display_name == "Ada"
    assert fetched.timezone == "America/New_York"


@pytest.mark.integration
def test_add_person_honors_morning_override(migrated_engine):
    repo = SqlAlchemyProfileRepository(migrated_engine)
    person = add_person(repo, name="Bo", timezone="America/New_York", morning="05:45")
    assert repo.get_person(person.profile_id).morning_prompt_local_time == time(5, 45)


@pytest.mark.integration
def test_add_group_creates_group_and_members(migrated_engine):
    repo = SqlAlchemyProfileRepository(migrated_engine)
    p1 = add_person(repo, name="Ada", timezone="America/New_York")
    p2 = add_person(repo, name="Bo", timezone="America/New_York")

    group = add_group(repo, label="Ada & Bo", members=[p1.profile_id, p2.profile_id])
    assert group.profile_id is not None
    assert repo.get_kind(group.profile_id) == ProfileKind.GROUP
    assert set(repo.list_group_members(group.profile_id)) == {
        p1.profile_id,
        p2.profile_id,
    }

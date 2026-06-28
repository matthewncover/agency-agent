import time as time_mod

import pytest
from agency_profile.domain.entities import GroupProfile, Person, ProfileDoc, ProfileKind
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
def test_create_and_get_person(repo):
    p = repo.create_person(Person(display_name="Alice", timezone="America/Los_Angeles"))
    assert p.profile_id is not None
    fetched = repo.get_person(p.profile_id)
    assert fetched.display_name == "Alice"
    assert fetched.timezone == "America/Los_Angeles"
    assert repo.get_kind(p.profile_id) == ProfileKind.PERSON


@pytest.mark.integration
def test_group_and_members(repo):
    p1 = repo.create_person(Person(display_name="Alice", timezone="America/New_York"))
    p2 = repo.create_person(Person(display_name="Bob", timezone="America/New_York"))
    p3 = repo.create_person(Person(display_name="Carol", timezone="America/New_York"))

    g = repo.create_group(
        GroupProfile(label="Alice & Bob"), [p1.profile_id, p2.profile_id]
    )
    assert g.profile_id is not None
    assert repo.get_kind(g.profile_id) == ProfileKind.GROUP
    assert set(repo.list_group_members(g.profile_id)) == {p1.profile_id, p2.profile_id}

    repo.add_group_member(g.profile_id, p3.profile_id)
    assert p3.profile_id in repo.list_group_members(g.profile_id)


@pytest.mark.integration
def test_profile_doc_upsert_and_updated_at_bump(repo):
    p = repo.create_person(Person(display_name="Alice", timezone="UTC"))
    doc1 = repo.upsert_profile_doc(ProfileDoc(person_id=p.profile_id, content="v1"))
    assert doc1.updated_at is not None

    time_mod.sleep(0.01)  # ensure clock advances
    doc2 = repo.upsert_profile_doc(ProfileDoc(person_id=p.profile_id, content="v2"))
    assert doc2.content == "v2"
    assert doc2.updated_at >= doc1.updated_at

    fetched = repo.get_profile_doc(p.profile_id)
    assert fetched.content == "v2"


@pytest.mark.integration
def test_profile_doc_person_only(repo):
    p1 = repo.create_person(Person(display_name="Alice", timezone="UTC"))
    p2 = repo.create_person(Person(display_name="Bob", timezone="UTC"))
    g = repo.create_group(GroupProfile(label="A & B"), [p1.profile_id, p2.profile_id])

    with pytest.raises(IntegrityError):
        repo.upsert_profile_doc(ProfileDoc(person_id=g.profile_id, content="bad"))


@pytest.mark.integration
def test_group_members_must_be_persons(repo):
    p1 = repo.create_person(Person(display_name="Alice", timezone="UTC"))
    p2 = repo.create_person(Person(display_name="Bob", timezone="UTC"))
    g = repo.create_group(GroupProfile(label="A & B"), [p1.profile_id, p2.profile_id])

    with pytest.raises(IntegrityError):
        repo.add_group_member(g.profile_id, g.profile_id)

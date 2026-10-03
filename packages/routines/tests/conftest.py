import pytest
from agency_profile.domain.entities import Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from routines.infrastructure.checklist_repo import SqlAlchemyChecklistRepository
from sqlalchemy import text


@pytest.fixture
def clean_db(migrated_engine):
    yield migrated_engine
    with migrated_engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE routines.item, routines.person_state, "
                "profile.person, profile.profile RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def profiles(clean_db):
    return SqlAlchemyProfileRepository(clean_db)


@pytest.fixture
def person_id(profiles):
    return profiles.create_person(
        Person(display_name="Matthew", timezone="America/Los_Angeles")
    ).profile_id


@pytest.fixture
def repo(clean_db):
    return SqlAlchemyChecklistRepository(clean_db)

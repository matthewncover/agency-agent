import pytest
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from sqlalchemy import text


@pytest.fixture
def repo(migrated_engine):
    yield SqlAlchemyProfileRepository(migrated_engine)
    with migrated_engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE profile.profile, profile.person, profile.group_profile, "
                "profile.group_member, profile.profile_doc RESTART IDENTITY CASCADE"
            )
        )

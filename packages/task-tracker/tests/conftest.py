import pytest
from agency_profile.domain.entities import Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from sqlalchemy import text

from task_tracker.infrastructure.adapters import (
    PgDailyLogRepositoryAdapter,
    PgSprintRepositoryAdapter,
    PgSystemMetaRepositoryAdapter,
    PgTaskRepositoryAdapter,
    PgTimeEntryRepositoryAdapter,
)
from task_tracker.infrastructure.task_query_client import PgTaskQueryClient

# `migrated_engine` (session-scoped, builds the agency_test DB + runs Alembic
# head) is provided by the repo-root conftest.py — shared across all packages.


@pytest.fixture(autouse=True)
def _clean_db(migrated_engine):
    yield
    with migrated_engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE "
                "tasktracker.time_entries, tasktracker.daily_logs, "
                "tasktracker.work_tasks, tasktracker.personal_tasks, "
                "tasktracker.sprints, tasktracker.system_meta, "
                "profile.profile_doc, profile.group_member, "
                "profile.group_profile, profile.person, profile.profile "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def person_id(migrated_engine):
    p = SqlAlchemyProfileRepository(migrated_engine).create_person(
        Person(display_name="t", timezone="America/Los_Angeles")
    )
    return p.profile_id


@pytest.fixture
def other_person_id(migrated_engine):
    p = SqlAlchemyProfileRepository(migrated_engine).create_person(
        Person(display_name="other", timezone="America/Los_Angeles")
    )
    return p.profile_id


@pytest.fixture
def task_repo(migrated_engine, person_id):
    return PgTaskRepositoryAdapter(migrated_engine, person_id)


@pytest.fixture
def time_entry_repo(migrated_engine):
    return PgTimeEntryRepositoryAdapter(migrated_engine)


@pytest.fixture
def sprint_repo(migrated_engine):
    return PgSprintRepositoryAdapter(migrated_engine)


@pytest.fixture
def daily_log_repo(migrated_engine, person_id):
    return PgDailyLogRepositoryAdapter(migrated_engine, person_id)


@pytest.fixture
def system_meta_repo(migrated_engine):
    return PgSystemMetaRepositoryAdapter(migrated_engine)


@pytest.fixture
def query_client(migrated_engine):
    return PgTaskQueryClient(migrated_engine)

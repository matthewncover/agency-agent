import sys
from pathlib import Path

# Make the tests/ directory importable so fakes.py can be imported as `from fakes import ...`
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from agency_profile.domain.entities import Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _clean_db(migrated_engine):
    yield
    with migrated_engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE "
                "goalbot.daily_plan_item, goalbot.daily_plan, "
                "goalbot.friction_log, goalbot.win_log, "
                "goalbot.visualization, "
                "goalbot.anticipated_obstacle, goalbot.goal_tag, "
                "goalbot.goal_version, goalbot.goal_state, "
                "goalbot.rotation_group, "
                "goalbot.goal, goalbot.chapter, "
                "goalbot.insight, goalbot.tag, "
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
def goal_repo(migrated_engine):
    return SqlAlchemyGoalRepository(migrated_engine)


@pytest.fixture
def plan_repo(migrated_engine):
    return SqlAlchemyPlanRepository(migrated_engine)


@pytest.fixture
def win_repo(migrated_engine):
    return SqlAlchemyWinRepository(migrated_engine)

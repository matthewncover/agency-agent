from datetime import date, timedelta

from agency_profile.domain.entities import Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from sqlalchemy import Engine

from goal_bot.server import build_use_cases


def _today() -> date:
    return date.today()


def seed_demo(
    engine: Engine,
    *,
    display_name: str = "Matthew",
    timezone: str = "America/Los_Angeles",
) -> int:
    pid = SqlAlchemyProfileRepository(engine).create_person(
        Person(display_name=display_name, timezone=timezone)
    ).profile_id

    uc = build_use_cases(engine)
    today = _today()
    ch = uc.create_chapter(pid, today, today + timedelta(weeks=10), "Q3")

    # daily/binary/need goals — bread-and-butter of the morning surface
    g1 = uc.create_goal(pid, "Move 20 minutes", chapter_id=ch)
    uc.create_goal_version(
        goal_id=g1, version_no=1, level="need",
        definition="20 continuous minutes of movement",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="energy + mood anchors every other habit",
    )

    g2 = uc.create_goal(pid, "Read 10 pages", chapter_id=ch)
    uc.create_goal_version(
        goal_id=g2, version_no=1, level="need",
        definition="10 pages of a current book",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="compound learning over time",
    )

    g3 = uc.create_goal(pid, "Write one sentence", chapter_id=ch)
    uc.create_goal_version(
        goal_id=g3, version_no=1, level="need",
        definition="one sentence toward a current project",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="creative momentum requires showing up daily",
    )

    # goal with both a need and a want version — exercises committed_level later
    g4 = uc.create_goal(pid, "Meditate", chapter_id=ch)
    uc.create_goal_version(
        goal_id=g4, version_no=1, level="need",
        definition="5 minutes of breath awareness",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="floor that maintains the practice on hard days",
    )
    uc.create_goal_version(
        goal_id=g4, version_no=2, level="want",
        definition="20 minutes with a timer",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="depth session when conditions are right",
    )

    # chapter-less goal — must surface in get_full_goal_list
    g5 = uc.create_goal(pid, "Review inbox", chapter_id=None)
    uc.create_goal_version(
        goal_id=g5, version_no=1, level="need",
        definition="clear to zero or defer everything",
        recurrence_type="daily", recurrence_config={},
        completion_type="binary", why="clear head for deep work",
    )

    return pid


if __name__ == "__main__":
    from agency_profile.infrastructure.engine import make_engine

    from goal_bot.config import Settings

    engine = make_engine(Settings().database_url)
    pid = seed_demo(engine)
    print(f"seeded person_id={pid}")
    engine.dispose()

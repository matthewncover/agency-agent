from datetime import date, timedelta

from agency_profile.domain.entities import Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from sqlalchemy import Engine

from goal_bot.server import build_use_cases


def _today() -> date:
    return date.today()


def seed_person(
    engine: Engine,
    *,
    display_name: str = "Matthew",
    timezone: str = "America/Los_Angeles",
) -> int:
    """Create a single person profile and return its id. No goals/chapters —
    this is the owner id real ingestion writes against."""
    return (
        SqlAlchemyProfileRepository(engine)
        .create_person(Person(display_name=display_name, timezone=timezone))
        .profile_id
    )


# --- the "toy dataset" ---
#
# A faithful reproduction of Matthew's real first ingested chapter (the 11
# goals below), plus two synthetic goals appended purely to cover combinations
# the real chapter doesn't exercise (daily/binary, and a chapter-less goal).
# This is the baseline you get from `just seed`; `just toy-reset` rebuilds it
# from a clean schema. Keep it faithful — when re-ingestion drifts the real
# chapter, refresh the verbatim rows here from the DB rather than inventing.

# Shared `why` strings (verbatim from the ingest — one per goal cluster).
_WHY_STEPS = (
    "gotta get that vitamin d for mood and sleep, walking relaxes my nervous "
    "system, gives my brain space to wander, cuts my brain fog after eating, and "
    "somehow both makes me more productive and reminds me I don't need to be "
    "productive all the time"
)
_WHY_WORKOUT = (
    "when I don't workout I feel gross. feeling gross has ripple effect consequences"
)
_WHY_ERRANDS = (
    "these are little thing that have been poking my brain little by little "
    "recently and if I clean the cruft I can close loops that make life feel like "
    "I have these really small but noticeable ankle weights on but having the "
    "weights on doesn't actually get me thick calves its just sludge on my willpower"
)

# Shared anticipated-obstacle lists (verbatim).
_STEP_OBS = [
    "waking up later and feeling rushed out the door - need to shift bedtime earlier",
    "feeling gassed after work - this is silly, walking isn't strenuous and is a "
    "genuine winddown",
    '"I got a bunch of steps in yesterday I\'m good today" - reminder that my '
    "parents walk 2x my steps every day",
]
_WORKOUT_OBS = [
    '"Muscles need breaks, I can take another day off" - this is a lie. the '
    "literature says its a lie",
    "feeling gassed - reminder that this is an insanely easy workout and it's the "
    "minimum",
    '"I don\'t have access to a pullup bar today" - great, do more pushups',
]
_ERRAND_OBS = ['"I\'m busy today with { bs }" - you can make small moves today']

# The eight oneoff/binary errands: (title, personal task_ref_id, extra obstacles).
_ERRANDS = [
    (
        "Renew passport",
        3,
        [
            "\"I'm not going to Slovenia so no rush on my passport\" - dawg, you don't "
            "know when you might need it",
        ],
    ),
    ("Re-register TSA precheck", 4, []),
    (
        "Register Bronco in CA",
        1,
        [
            '"I can get away with Arizona plates in CA" - '
            "until you dont get away with it?",
        ],
    ),
    ("Cancel boxing membership", 71, []),
    ("Get money from Brian Lee", 50, []),
    ("Capital One statements audit", 72, []),
    ("Flight expensing", 62, []),
    ("Cancel Slovenia plans", 5, []),
]


def _real_chapter_goals(ch: int) -> list[dict]:
    """The 11 goals from the real first chapter, as create_goals specs."""
    goals: list[dict] = [
        {
            "title": "step goal",
            "chapter_id": ch,
            "versions": [
                {
                    "level": "need",
                    "definition": "5,000 steps",
                    "why": _WHY_STEPS,
                    "recurrence_type": "daily",
                    "recurrence_config": {},
                    "completion_type": "quantity",
                    "target_quantity": 5000,
                    "quantity_unit": "steps",
                    "obstacles": _STEP_OBS,
                },
                {
                    "level": "want",
                    "definition": "7,000 steps",
                    "why": _WHY_STEPS,
                    "recurrence_type": "daily",
                    "recurrence_config": {},
                    "completion_type": "quantity",
                    "target_quantity": 7000,
                    "quantity_unit": "steps",
                    "obstacles": _STEP_OBS,
                },
            ],
        },
        {
            "title": "pushups",
            "chapter_id": ch,
            "versions": [
                {
                    "level": "need",
                    "definition": "50 pushups (4s eccentric), every 4 days",
                    "why": _WHY_WORKOUT,
                    "recurrence_type": "interval",
                    "recurrence_config": {"every_days": 4},
                    "completion_type": "quantity",
                    "target_quantity": 50,
                    "quantity_unit": "reps",
                    "obstacles": _WORKOUT_OBS,
                },
                {
                    "level": "want",
                    "definition": "75 pushups (4s eccentric), every 4 days",
                    "why": _WHY_WORKOUT,
                    "recurrence_type": "interval",
                    "recurrence_config": {"every_days": 4},
                    "completion_type": "quantity",
                    "target_quantity": 75,
                    "quantity_unit": "reps",
                    "obstacles": _WORKOUT_OBS,
                },
            ],
        },
        {
            "title": "pull-ups",
            "chapter_id": ch,
            "versions": [
                {
                    "level": "need",
                    "definition": "20 pull-ups (4s eccentric), every 4 days",
                    "why": _WHY_WORKOUT,
                    "recurrence_type": "interval",
                    "recurrence_config": {"every_days": 4},
                    "completion_type": "quantity",
                    "target_quantity": 20,
                    "quantity_unit": "reps",
                    "obstacles": _WORKOUT_OBS,
                },
                {
                    "level": "want",
                    "definition": "30 pull-ups (4s eccentric), every 4 days",
                    "why": _WHY_WORKOUT,
                    "recurrence_type": "interval",
                    "recurrence_config": {"every_days": 4},
                    "completion_type": "quantity",
                    "target_quantity": 30,
                    "quantity_unit": "reps",
                    "obstacles": _WORKOUT_OBS,
                },
            ],
        },
    ]
    for title, ref_id, extra_obs in _ERRANDS:
        goals.append(
            {
                "title": title,
                "chapter_id": ch,
                "versions": [
                    {
                        "level": "need",
                        "definition": title,
                        "why": _WHY_ERRANDS,
                        "recurrence_type": "oneoff",
                        "recurrence_config": {},
                        "completion_type": "binary",
                        "task_ref_source": "personal",
                        "task_ref_id": ref_id,
                        "obstacles": _ERRAND_OBS + extra_obs,
                    }
                ],
            }
        )
    return goals


def _coverage_goals(ch: int) -> list[dict]:
    """Synthetic goals appended for cases the real chapter doesn't cover:
    a daily/binary need+want pair, and a chapter-less goal (must still surface
    in get_full_goal_list)."""
    return [
        {
            "title": "Meditate",
            "chapter_id": ch,
            "versions": [
                {
                    "level": "need",
                    "definition": "5 minutes of breath awareness",
                    "recurrence_type": "daily",
                    "recurrence_config": {},
                    "completion_type": "binary",
                    "why": "floor that maintains the practice on hard days",
                },
                {
                    "level": "want",
                    "definition": "20 minutes with a timer",
                    "recurrence_type": "daily",
                    "recurrence_config": {},
                    "completion_type": "binary",
                    "why": "depth session when conditions are right",
                },
            ],
        },
        {
            "title": "Review inbox",
            "chapter_id": None,
            "versions": [
                {
                    "level": "need",
                    "definition": "clear to zero or defer everything",
                    "recurrence_type": "daily",
                    "recurrence_config": {},
                    "completion_type": "binary",
                    "why": "clear head for deep work",
                }
            ],
        },
    ]


def seed_demo(
    engine: Engine,
    *,
    display_name: str = "Matthew",
    timezone: str = "America/Los_Angeles",
) -> int:
    """Seed the toy dataset: the real first chapter plus coverage goals."""
    pid = seed_person(engine, display_name=display_name, timezone=timezone)

    uc = build_use_cases(engine)
    today = _today()
    # Real chapter ran 2026-06-15 → 2026-07-20 (~5 weeks, ~2 weeks in by 6/28).
    # Anchor relative to today so the toy chapter is always active when seeded.
    ch = uc.create_chapter(
        pid,
        today - timedelta(weeks=2),
        today + timedelta(weeks=3),
        None,
    )

    created = uc.create_goals(pid, _real_chapter_goals(ch) + _coverage_goals(ch))

    # Rotation group (ADR-0016): pushups and pull-ups share one alternating
    # rhythm (push → rest → pull → rest); the group owns the cadence, the two
    # goals keep their own need/want bars and rep logging.
    by_title = {g["title"]: g["gid"] for g in created}
    uc.create_rotation_group(
        pid,
        "calisthenics",
        [
            {"goal_id": by_title["pushups"]},
            {"rest": True},
            {"goal_id": by_title["pull-ups"]},
            {"rest": True},
        ],
    )

    return pid


if __name__ == "__main__":
    import argparse

    from agency_profile.infrastructure.engine import make_engine

    from goal_bot.config import Settings

    parser = argparse.ArgumentParser(description="Seed goal-bot data.")
    parser.add_argument(
        "--person-only",
        action="store_true",
        help="Create just the person (the ingestion owner), no demo goals.",
    )
    parser.add_argument("--name", default="Matthew")
    parser.add_argument("--tz", default="America/Los_Angeles")
    args = parser.parse_args()

    engine = make_engine(Settings().database_url)
    seed = seed_person if args.person_only else seed_demo
    pid = seed(engine, display_name=args.name, timezone=args.tz)
    print(f"seeded person_id={pid}")
    engine.dispose()

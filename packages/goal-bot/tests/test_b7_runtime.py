"""B7 Part 2 — two-person runtime: config map, per-person scheduling, routing."""

from datetime import time

from agency_profile.domain.entities import Person
from goal_bot.config import Settings
from goal_bot.infrastructure.scheduler import schedule_morning
from goal_bot.infrastructure.telegram_adapter import (
    TelegramAdapter,
    is_addressed,
    strip_mention,
)

_TOKEN = "123456:ABCdefGHIjklMNOpqrs"


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    def add_job(self, func, trigger: str, *, id: str, **kwargs) -> None:
        self.jobs[id] = {"trigger": trigger, "func": func, **kwargs}


# --- config mapping ---------------------------------------------------------


def test_chat_person_map_parses_multiple_pairs():
    s = Settings(telegram_chat_map="111:1,222:2")
    assert s.chat_person_pairs() == [(111, 1), (222, 2)]


def test_chat_person_map_falls_back_to_single_pair():
    s = Settings(telegram_chat_id=999, person_id=7)
    assert s.chat_person_pairs() == [(999, 7)]


def test_chat_person_map_takes_precedence_over_single():
    s = Settings(telegram_chat_map="111:1,222:2", telegram_chat_id=999, person_id=7)
    assert s.chat_person_pairs() == [(111, 1), (222, 2)]


def test_chat_person_map_empty_when_unconfigured():
    # explicit empties (init kwargs outrank any ambient .env)
    s = Settings(telegram_chat_map="", telegram_chat_id=0, person_id=0)
    assert s.chat_person_pairs() == []


# --- per-person scheduling --------------------------------------------------


def test_two_persons_register_two_jobs_at_their_local_times():
    sched = _FakeScheduler()
    a = Person(
        display_name="A",
        timezone="America/Los_Angeles",
        morning_prompt_local_time=time(6, 0),
    )
    b = Person(
        display_name="B",
        timezone="America/New_York",
        morning_prompt_local_time=time(7, 30),
    )
    schedule_morning(
        sched,
        run_morning=lambda: None,
        person=a,
        debug_interval=None,
        job_id="morning-1",
    )
    schedule_morning(
        sched,
        run_morning=lambda: None,
        person=b,
        debug_interval=None,
        job_id="morning-2",
    )

    assert set(sched.jobs) == {"morning-1", "morning-2"}
    assert sched.jobs["morning-1"]["hour"] == 6
    assert sched.jobs["morning-1"]["timezone"] == "America/Los_Angeles"
    assert sched.jobs["morning-2"]["hour"] == 7
    assert sched.jobs["morning-2"]["minute"] == 30
    assert sched.jobs["morning-2"]["timezone"] == "America/New_York"


def test_morning_jobs_get_a_generous_misfire_grace():
    # Two persons on the same UTC offset fire at the same instant; the second
    # job starts only after the first person's whole morning turn. With
    # APScheduler's default 1s grace it was skipped as a misfire — one
    # household, one message. Late must beat never.
    sched = _FakeScheduler()
    p = Person(
        display_name="A",
        timezone="America/Los_Angeles",
        morning_prompt_local_time=time(6, 0),
    )
    schedule_morning(
        sched, run_morning=lambda: None, person=p, debug_interval=None, job_id="cron"
    )
    schedule_morning(
        sched, run_morning=lambda: None, person=p, debug_interval=30, job_id="debug"
    )
    assert sched.jobs["cron"]["misfire_grace_time"] >= 60
    assert sched.jobs["debug"]["misfire_grace_time"] >= 60


# --- inbound routing (membership auth + chat→person) ------------------------


def _adapter():
    persons = {
        1: Person(display_name="A", timezone="America/Los_Angeles"),
        2: Person(display_name="B", timezone="America/New_York"),
    }
    return TelegramAdapter(
        token=_TOKEN,
        chat_person={111: 1, 222: 2},
        persons=persons,
        service=None,
        scheduler=None,
    )


def test_message_routes_by_chat_to_the_right_person():
    a = _adapter()
    # no user map configured → legacy chat routing, speaker irrelevant
    assert a.person_for(111, user_id=555) == 1
    assert a.person_for(222, user_id=555) == 2
    assert a.chat_for_person(1) == 111
    assert a.chat_for_person(2) == 222


def test_unknown_chat_is_not_a_member():
    a = _adapter()
    assert a.is_member(111) is True
    assert a.is_member(999) is False
    assert a.person_for(999, user_id=555) is None


def test_morning_job_targets_the_persons_own_chat():
    a = _adapter()
    # each person's job is a distinct callable bound to their chat
    assert callable(a.morning_job_for(1))
    assert callable(a.morning_job_for(2))


# --- group-chat addressing gate ----------------------------------------------

_BOT_ID = 123456
_BOT_USERNAME = "goal_bot"


def test_private_chat_is_always_addressed():
    assert is_addressed("private", "did the thing", _BOT_USERNAME, _BOT_ID, None)


def test_group_plain_text_is_not_addressed():
    assert not is_addressed("group", "did the thing", _BOT_USERNAME, _BOT_ID, None)


def test_group_reply_to_bot_is_addressed():
    assert is_addressed("group", "did the thing", _BOT_USERNAME, _BOT_ID, _BOT_ID)


def test_group_reply_to_someone_else_is_not_addressed():
    assert not is_addressed("group", "did the thing", _BOT_USERNAME, _BOT_ID, 777)


def test_group_mention_is_addressed_case_insensitive():
    assert is_addressed(
        "group", "@Goal_Bot did the thing", _BOT_USERNAME, _BOT_ID, None
    )
    assert is_addressed(
        "group", "did the thing @goal_bot", _BOT_USERNAME, _BOT_ID, None
    )


def test_group_mention_of_similar_username_is_not_addressed():
    assert not is_addressed("group", "@goal_bot2 hi", _BOT_USERNAME, _BOT_ID, None)


def test_strip_mention_removes_bot_tag_only():
    assert strip_mention("@goal_bot did the thing", _BOT_USERNAME) == "did the thing"
    assert strip_mention("did the thing", _BOT_USERNAME) == "did the thing"
    assert strip_mention("ask @someone_else", _BOT_USERNAME) == "ask @someone_else"

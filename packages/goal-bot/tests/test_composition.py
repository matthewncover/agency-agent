"""
Tests for the scheduler wiring in composition — no network, no DB.
Tests schedule_morning directly (the part build_app delegates to).
"""

from datetime import time

from agency_profile.domain.entities import Person
from goal_bot.infrastructure.scheduler import schedule_morning


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    def add_job(self, func, trigger: str, *, id: str, **kwargs) -> None:
        self.jobs[id] = {"trigger": trigger, "func": func, **kwargs}


async def _noop() -> None: ...


def test_schedule_interval_when_debug_interval_set():
    sched = _FakeScheduler()
    person = Person(
        display_name="t",
        timezone="America/Los_Angeles",
        morning_prompt_local_time=time(6, 0),
    )
    schedule_morning(sched, run_morning=_noop, person=person, debug_interval=5)

    job = sched.jobs["morning"]
    assert job["trigger"] == "interval"
    assert job["seconds"] == 5


def test_schedule_cron_at_person_local_time():
    sched = _FakeScheduler()
    person = Person(
        display_name="t",
        timezone="America/Los_Angeles",
        morning_prompt_local_time=time(7, 30),
    )
    schedule_morning(sched, run_morning=_noop, person=person, debug_interval=None)

    job = sched.jobs["morning"]
    assert job["trigger"] == "cron"
    assert job["hour"] == 7
    assert job["minute"] == 30
    assert job["timezone"] == "America/Los_Angeles"

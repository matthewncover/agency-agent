from agency_profile.domain.entities import Person

# APScheduler's default grace is 1 second: a job that can't *start* within 1s
# of its slot is skipped outright. Two persons whose local mornings land on
# the same UTC instant (e.g. PDT + MST) share one event loop, so the second
# job only starts after the first person's whole morning turn — several
# seconds later — and was being dropped as a "misfire". Late is fine; never
# is not.
MISFIRE_GRACE_SECONDS = 3600


def schedule_morning(
    scheduler,
    *,
    run_morning,
    person: Person,
    debug_interval: int | None,
    job_id: str = "morning",
) -> None:
    """Register one morning job for one person. Called once per person (B7), so
    each fires at *their* local morning time; job_id must be unique per person."""
    if debug_interval:
        scheduler.add_job(
            run_morning,
            "interval",
            seconds=debug_interval,
            id=job_id,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )
    else:
        hh = person.morning_prompt_local_time.hour
        mm = person.morning_prompt_local_time.minute
        scheduler.add_job(
            run_morning,
            "cron",
            hour=hh,
            minute=mm,
            timezone=person.timezone,
            id=job_id,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

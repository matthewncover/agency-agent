from agency_profile.domain.entities import Person


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
        scheduler.add_job(run_morning, "interval", seconds=debug_interval, id=job_id)
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
        )

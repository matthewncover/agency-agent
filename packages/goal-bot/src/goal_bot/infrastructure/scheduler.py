from agency_profile.domain.entities import Person


def schedule_morning(
    scheduler,
    *,
    run_morning,
    person: Person,
    debug_interval: int | None,
) -> None:
    if debug_interval:
        scheduler.add_job(run_morning, "interval", seconds=debug_interval, id="morning")
    else:
        hh = person.morning_prompt_local_time.hour
        mm = person.morning_prompt_local_time.minute
        scheduler.add_job(
            run_morning,
            "cron",
            hour=hh,
            minute=mm,
            timezone=person.timezone,
            id="morning",
        )

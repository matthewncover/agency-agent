"""B7 Part 1 — identity provisioning CLI.

Identity is human-owned (ADR-0011 spirit): persons and groups are created only
by an explicit human act, never by the daily loop or ingestion. This is the
small, human-run path the ingestion/ritual grants deliberately don't expose.

    python -m goal_bot.provision add-person --name Ada --timezone America/New_York
    python -m goal_bot.provision add-group --label "Ada & Bo" --members 1,2

Built entirely over the existing agency_profile repo — no new schema.
"""

from datetime import time

from agency_profile.application.ports import ProfileRepositoryPort
from agency_profile.domain.entities import GroupProfile, Person


def _parse_morning(value: str) -> time:
    """Parse an HH:MM morning time. Raises ValueError on malformed input."""
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _parse_members(value: str) -> list[int]:
    """Parse a comma-separated list of person ids into ints."""
    ids = [part.strip() for part in value.split(",") if part.strip()]
    if not ids:
        raise ValueError("--members must list at least one person id")
    return [int(i) for i in ids]


def add_person(
    repo: ProfileRepositoryPort,
    *,
    name: str,
    timezone: str,
    morning: str | None = None,
) -> Person:
    """Create a profile.person and return it (with its assigned profile_id)."""
    person = Person(display_name=name, timezone=timezone)
    if morning:
        person.morning_prompt_local_time = _parse_morning(morning)
    return repo.create_person(person)


def add_group(
    repo: ProfileRepositoryPort,
    *,
    label: str,
    members: list[int],
) -> GroupProfile:
    """Create a group_profile + group_member rows and return the group."""
    return repo.create_group(GroupProfile(label=label), members)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from agency_profile.infrastructure.adapters.profile_repo import (
        SqlAlchemyProfileRepository,
    )
    from agency_profile.infrastructure.engine import make_engine

    from goal_bot.config import Settings

    parser = argparse.ArgumentParser(
        prog="goal_bot.provision",
        description="Human-run identity provisioning (persons and groups).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_person = sub.add_parser("add-person", help="Create a person profile.")
    p_person.add_argument("--name", required=True)
    p_person.add_argument(
        "--timezone", required=True, help="IANA tz, e.g. America/New_York"
    )
    p_person.add_argument(
        "--morning",
        default=None,
        metavar="HH:MM",
        help="Morning prompt local time (default 06:00).",
    )

    p_group = sub.add_parser("add-group", help="Create a group + members.")
    p_group.add_argument("--label", required=True)
    p_group.add_argument(
        "--members",
        required=True,
        metavar="ID,ID",
        help="Comma-separated person ids to add as members.",
    )

    args = parser.parse_args(argv)

    engine = make_engine(Settings().database_url)
    repo = SqlAlchemyProfileRepository(engine)
    try:
        if args.command == "add-person":
            person = add_person(
                repo, name=args.name, timezone=args.timezone, morning=args.morning
            )
            print(f"person_id={person.profile_id}")
        elif args.command == "add-group":
            group = add_group(
                repo, label=args.label, members=_parse_members(args.members)
            )
            print(f"group_profile_id={group.profile_id}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

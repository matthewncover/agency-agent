from sqlalchemy import Engine, insert, select, update

from agency_profile.application.ports import ProfileRepositoryPort
from agency_profile.domain.entities import GroupProfile, Person, ProfileDoc, ProfileKind
from agency_profile.infrastructure import tables as t


def _person(row) -> Person:
    return Person(
        profile_id=row.profile_id, display_name=row.display_name,
        timezone=row.timezone, morning_prompt_local_time=row.morning_prompt_local_time,
    )


class SqlAlchemyProfileRepository(ProfileRepositoryPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_person(self, person: Person) -> Person:
        with self._engine.begin() as c:
            pid = c.execute(
                insert(t.profile).values(kind="person").returning(t.profile.c.id)
            ).scalar_one()
            c.execute(insert(t.person).values(
                profile_id=pid, display_name=person.display_name,
                timezone=person.timezone,
                morning_prompt_local_time=person.morning_prompt_local_time,
            ))
            row = c.execute(select(t.person).where(t.person.c.profile_id == pid)).one()
        return _person(row)

    def create_group(
        self, group: GroupProfile, member_person_ids: list[int]
    ) -> GroupProfile:
        with self._engine.begin() as c:
            pid = c.execute(
                insert(t.profile).values(kind="group").returning(t.profile.c.id)
            ).scalar_one()
            c.execute(insert(t.group_profile).values(profile_id=pid, label=group.label))
            for m in member_person_ids:
                c.execute(insert(t.group_member).values(
                    group_profile_id=pid, member_person_id=m))
        return GroupProfile(profile_id=pid, label=group.label)

    def get_person(self, profile_id: int) -> Person | None:
        with self._engine.connect() as c:
            row = c.execute(select(t.person).where(
                t.person.c.profile_id == profile_id)).one_or_none()
        return _person(row) if row else None

    def get_kind(self, profile_id: int) -> ProfileKind | None:
        with self._engine.connect() as c:
            k = c.execute(select(t.profile.c.kind).where(
                t.profile.c.id == profile_id)).scalar_one_or_none()
        return ProfileKind(k) if k else None

    def list_group_members(self, group_profile_id: int) -> list[int]:
        with self._engine.connect() as c:
            rows = c.execute(select(t.group_member.c.member_person_id).where(
                t.group_member.c.group_profile_id == group_profile_id)).scalars().all()
        return list(rows)

    def add_group_member(self, group_profile_id: int, member_person_id: int) -> None:
        with self._engine.begin() as c:
            c.execute(insert(t.group_member).values(
                group_profile_id=group_profile_id, member_person_id=member_person_id))

    def upsert_profile_doc(self, doc: ProfileDoc) -> ProfileDoc:
        with self._engine.begin() as c:
            existing = c.execute(select(t.profile_doc.c.person_id).where(
                t.profile_doc.c.person_id == doc.person_id)).one_or_none()
            if existing:
                c.execute(update(t.profile_doc)
                          .where(t.profile_doc.c.person_id == doc.person_id)
                          .values(content=doc.content))
            else:
                c.execute(insert(t.profile_doc).values(
                    person_id=doc.person_id, content=doc.content))
            row = c.execute(select(t.profile_doc).where(
                t.profile_doc.c.person_id == doc.person_id)).one()
        return ProfileDoc(
            person_id=row.person_id, content=row.content, updated_at=row.updated_at
        )

    def get_profile_doc(self, person_id: int) -> ProfileDoc | None:
        with self._engine.connect() as c:
            row = c.execute(select(t.profile_doc).where(
                t.profile_doc.c.person_id == person_id)).one_or_none()
        return ProfileDoc(person_id=row.person_id, content=row.content,
                          updated_at=row.updated_at) if row else None

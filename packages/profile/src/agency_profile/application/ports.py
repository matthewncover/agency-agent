from abc import ABC, abstractmethod

from agency_profile.domain.entities import GroupProfile, Person, ProfileDoc, ProfileKind


class ProfileRepositoryPort(ABC):
    @abstractmethod
    def create_person(self, person: Person) -> Person: ...

    @abstractmethod
    def create_group(
        self, group: GroupProfile, member_person_ids: list[int]
    ) -> GroupProfile: ...

    @abstractmethod
    def get_person(self, profile_id: int) -> Person | None: ...

    @abstractmethod
    def get_kind(self, profile_id: int) -> ProfileKind | None: ...

    @abstractmethod
    def list_group_members(self, group_profile_id: int) -> list[int]: ...

    @abstractmethod
    def add_group_member(
        self, group_profile_id: int, member_person_id: int
    ) -> None: ...

    @abstractmethod
    def upsert_profile_doc(self, doc: ProfileDoc) -> ProfileDoc: ...

    @abstractmethod
    def get_profile_doc(self, person_id: int) -> ProfileDoc | None: ...

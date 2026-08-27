from datetime import date

from task_tracker.domain.entities import (
    PersonalTaskEntity,
    PersonalTaskStatus,
)


class PersonalTaskFactory:
    @staticmethod
    def create(
        title: str,
        tier: int | None = None,
        status: PersonalTaskStatus = PersonalTaskStatus.NOT_STARTED,
        deadline: date | None = None,
        parent_task_id: int | None = None,
        is_commitment: bool = False,
        commitment_notes: str | None = None,
        priority_rank: int | None = None,
        pinned: bool = False,
        private: bool = False,
        notes: str | None = None,
    ) -> PersonalTaskEntity:
        return PersonalTaskEntity(
            title=title,
            tier=tier,
            status=status,
            deadline=deadline,
            parent_task_id=parent_task_id,
            is_commitment=is_commitment,
            commitment_notes=commitment_notes,
            priority_rank=priority_rank,
            pinned=pinned,
            private=private,
            notes=notes,
        )

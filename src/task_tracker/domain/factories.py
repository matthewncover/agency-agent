from datetime import date

from task_tracker.domain.entities import (
    CommitmentLevel,
    JnBucket,
    PersonalTaskEntity,
    PersonalTaskStatus,
    WorkTaskEntity,
    WorkTaskStatus,
)


class WorkTaskFactory:
    @staticmethod
    def create(
        title: str,
        ods_ticket: str | None = None,
        sprint_id: str | None = None,
        commitment_level: CommitmentLevel | None = None,
        jn_bucket: JnBucket | None = None,
        status: WorkTaskStatus = WorkTaskStatus.NOT_STARTED,
        estimate_hours: float | None = None,
        deadline: date | None = None,
        parent_task_id: int | None = None,
        is_commitment: bool = False,
        commitment_notes: str | None = None,
        priority_rank: int | None = None,
        notes: str | None = None,
    ) -> WorkTaskEntity:
        return WorkTaskEntity(
            title=title,
            ods_ticket=ods_ticket,
            sprint_id=sprint_id,
            commitment_level=commitment_level,
            jn_bucket=jn_bucket,
            status=status,
            estimate_hours=estimate_hours,
            deadline=deadline,
            parent_task_id=parent_task_id,
            is_commitment=is_commitment,
            commitment_notes=commitment_notes,
            priority_rank=priority_rank,
            notes=notes,
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
            notes=notes,
        )

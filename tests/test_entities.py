from datetime import date

from task_tracker.domain.entities import (
    CommitmentLevel,
    JnBucket,
    PersonalTaskEntity,
    PersonalTaskStatus,
    WorkTaskEntity,
    WorkTaskStatus,
)
from task_tracker.domain.factories import PersonalTaskFactory, WorkTaskFactory


class TestWorkTaskEntity:
    def test_defaults(self):
        task = WorkTaskEntity(title="Test task")
        assert task.status == WorkTaskStatus.NOT_STARTED
        assert task.is_commitment is False
        assert task.children == []
        assert task.days_carried is None
        assert task.actual_hours is None

    def test_all_fields(self):
        task = WorkTaskEntity(
            title="ODS-1234 feature",
            ods_ticket="ODS-1234",
            sprint_id="2026-03-03",
            commitment_level=CommitmentLevel.SPRINT_COMMITTED,
            jn_bucket=JnBucket.DEVELOPMENT,
            status=WorkTaskStatus.IN_PROGRESS,
            estimate_hours=4.0,
            deadline=date(2026, 3, 5),
            is_commitment=True,
            commitment_notes="Promised to Sarah by Friday",
            priority_rank=1,
        )
        assert task.commitment_level == "sprint_committed"
        assert task.jn_bucket == "development"


class TestPersonalTaskEntity:
    def test_defaults(self):
        task = PersonalTaskEntity(title="Buy groceries")
        assert task.status == PersonalTaskStatus.NOT_STARTED
        assert task.pinned is False
        assert task.tier is None

    def test_tier3_pinned(self):
        task = PersonalTaskEntity(title="Learn Rust", tier=3, pinned=True)
        assert task.pinned is True
        assert task.tier == 3


class TestWorkTaskFactory:
    def test_create_minimal(self):
        task = WorkTaskFactory.create(title="Do thing")
        assert task.title == "Do thing"
        assert task.status == WorkTaskStatus.NOT_STARTED

    def test_create_with_fields(self):
        task = WorkTaskFactory.create(
            title="Sprint task",
            sprint_id="2026-03-03",
            commitment_level=CommitmentLevel.SPRINT_COMMITTED,
            jn_bucket=JnBucket.DEVELOPMENT,
        )
        assert task.sprint_id == "2026-03-03"
        assert task.commitment_level == CommitmentLevel.SPRINT_COMMITTED


class TestPersonalTaskFactory:
    def test_create_minimal(self):
        task = PersonalTaskFactory.create(title="Errand")
        assert task.title == "Errand"

    def test_create_tier1(self):
        task = PersonalTaskFactory.create(
            title="File taxes",
            tier=1,
            deadline=date(2026, 4, 15),
            is_commitment=True,
        )
        assert task.tier == 1
        assert task.is_commitment is True

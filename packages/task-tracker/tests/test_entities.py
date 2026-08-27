from datetime import date

from task_tracker.domain.entities import (
    PersonalTaskEntity,
    PersonalTaskStatus,
)
from task_tracker.domain.factories import PersonalTaskFactory


class TestPersonalTaskEntity:
    def test_defaults(self):
        task = PersonalTaskEntity(title="Buy groceries")
        assert task.status == PersonalTaskStatus.NOT_STARTED
        assert task.pinned is False
        assert task.tier is None
        assert task.is_commitment is False
        assert task.children == []
        assert task.days_carried is None

    def test_tier3_pinned(self):
        task = PersonalTaskEntity(title="Learn Rust", tier=3, pinned=True)
        assert task.pinned is True
        assert task.tier == 3


class TestPersonalTaskFactory:
    def test_create_minimal(self):
        task = PersonalTaskFactory.create(title="Errand")
        assert task.title == "Errand"
        assert task.status == PersonalTaskStatus.NOT_STARTED

    def test_create_tier1(self):
        task = PersonalTaskFactory.create(
            title="File taxes",
            tier=1,
            deadline=date(2026, 4, 15),
            is_commitment=True,
        )
        assert task.tier == 1
        assert task.is_commitment is True

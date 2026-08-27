from datetime import date

from task_tracker.application.use_cases import (
    BatchUpdateTasksUseCase,
    CompleteTaskUseCase,
    CreateTasksUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetOpenTasksUseCase,
    GetTaskDetailUseCase,
    GetTrackerDataUseCase,
    NukeTaskUseCase,
    UpdateTaskUseCase,
)
from task_tracker.domain.entities import PersonalTaskStatus


class TestCreateTaskUseCase:
    def test_create_task(self, task_repo):
        uc = CreateTaskUseCase(task_repo)
        task = uc.execute(title="Buy groceries", tier=2)
        assert task.id is not None
        assert task.tier == 2


class TestCreateTasksUseCase:
    def test_batch_create(self, task_repo):
        uc = CreateTasksUseCase(task_repo)
        tasks = uc.execute(
            [
                {"title": "Task 1", "tier": 1},
                {"title": "Task 2", "tier": 2},
                {"title": "Task 3"},
            ]
        )
        assert len(tasks) == 3


class TestGetTaskDetailUseCase:
    def test_days_carried_computed(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute(title="Project")
        uc = GetTaskDetailUseCase(task_repo)
        detail = uc.execute(task.id)
        assert detail.days_carried is not None  # Just created, so 0


class TestCompleteTaskUseCase:
    def test_complete_task(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute(title="To complete")
        uc = CompleteTaskUseCase(task_repo)
        completed = uc.execute(task.id)
        assert completed.status == PersonalTaskStatus.DONE
        assert completed.completed_at is not None


class TestNukeTaskUseCase:
    def test_nuke_task(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute(title="To nuke")
        uc = NukeTaskUseCase(task_repo)
        nuked = uc.execute(task.id)
        assert nuked.status == "nuked"


class TestDeleteTaskUseCase:
    def test_soft_delete(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute(title="Duplicate")
        uc = DeleteTaskUseCase(task_repo)
        assert uc.execute(task.id) is True
        assert task_repo.get_personal_task(task.id) is None


class TestUpdateTaskUseCase:
    def test_update_fields(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute(title="Original")
        uc = UpdateTaskUseCase(task_repo)
        updated = uc.execute(
            task.id,
            title="Updated",
            status="in_progress",
        )
        assert updated.title == "Updated"
        assert updated.status == PersonalTaskStatus.IN_PROGRESS


class TestBatchUpdateTasksUseCase:
    def test_batch_update(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        t1 = create.execute(title="Task 1", tier=1)
        t2 = create.execute(title="Task 2", tier=2)
        uc = BatchUpdateTasksUseCase(task_repo)
        results = uc.execute(
            [
                {"id": t1.id, "status": "in_progress"},
                {"id": t2.id, "status": "in_progress"},
            ]
        )
        assert results[0].status == "in_progress"
        assert results[1].status == "in_progress"


class TestGetOpenTasksUseCase:
    def test_open_only(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        create.execute(title="Open task", tier=1)
        done = create.execute(title="Done task", tier=1)
        CompleteTaskUseCase(task_repo).execute(done.id)
        uc = GetOpenTasksUseCase(task_repo)
        assert [t.title for t in uc.execute()] == ["Open task"]


class TestGetTrackerDataUseCase:
    def test_returns_all_sections(
        self,
        task_repo,
        daily_log_repo,
        system_meta_repo,
    ):
        create = CreateTaskUseCase(task_repo)
        create.execute(title="Personal task", tier=1)

        uc = GetTrackerDataUseCase(task_repo, daily_log_repo, system_meta_repo)
        data = uc.execute()
        assert "personal" in data
        assert "daily_log" in data
        assert "tier3_review_due" in data
        assert "work" not in data
        assert "sprint" not in data
        assert data["tier3_review_due"] is True  # Never reviewed

    def test_tier3_review_not_due(
        self,
        task_repo,
        daily_log_repo,
        system_meta_repo,
    ):
        system_meta_repo.set("last_tier3_review", str(date.today()))
        uc = GetTrackerDataUseCase(task_repo, daily_log_repo, system_meta_repo)
        data = uc.execute()
        assert data["tier3_review_due"] is False

from datetime import date

from task_tracker.application.use_cases import (
    BatchUpdateTasksUseCase,
    CompleteTaskUseCase,
    CreateTasksUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetOpenTasksUseCase,
    GetSprintTasksUseCase,
    GetTaskDetailUseCase,
    GetTrackerDataUseCase,
    NukeTaskUseCase,
    SetActiveSprintUseCase,
    UpdateTaskUseCase,
)
from task_tracker.domain.entities import (
    JnBucket,
    SprintEntity,
    TimeEntryEntity,
    WorkTaskStatus,
)


class TestCreateTaskUseCase:
    def test_create_work_task(self, task_repo):
        uc = CreateTaskUseCase(task_repo)
        task = uc.execute(
            "work",
            title="Build API",
            jn_bucket="development",
        )
        assert task.id is not None
        assert task.title == "Build API"

    def test_create_personal_task(self, task_repo):
        uc = CreateTaskUseCase(task_repo)
        task = uc.execute("personal", title="Buy groceries", tier=2)
        assert task.id is not None
        assert task.tier == 2

    def test_invalid_type(self, task_repo):
        uc = CreateTaskUseCase(task_repo)
        try:
            uc.execute("invalid", title="Nope")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestCreateTasksUseCase:
    def test_batch_create(self, task_repo):
        uc = CreateTasksUseCase(task_repo)
        tasks = uc.execute(
            [
                {"type": "work", "title": "Task 1"},
                {"type": "work", "title": "Task 2"},
                {"type": "personal", "title": "Personal 1", "tier": 1},
            ]
        )
        assert len(tasks) == 3


class TestGetTaskDetailUseCase:
    def test_work_task_with_actual_hours(self, task_repo, time_entry_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="Feature")
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date.today(),
                duration_minutes=120,
                jn_bucket=JnBucket.DEVELOPMENT,
            )
        )
        uc = GetTaskDetailUseCase(task_repo, time_entry_repo)
        detail = uc.execute(task.id, "work")
        assert detail.actual_hours == 2.0
        assert detail.days_carried is not None  # Just created, so 0


class TestCompleteTaskUseCase:
    def test_complete_work_task(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="To complete")
        uc = CompleteTaskUseCase(task_repo)
        completed = uc.execute(task.id, "work")
        assert completed.status == WorkTaskStatus.DONE
        assert completed.completed_at is not None


class TestNukeTaskUseCase:
    def test_nuke_work_task(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="To nuke")
        uc = NukeTaskUseCase(task_repo)
        nuked = uc.execute(task.id, "work")
        assert nuked.status == "nuked"


class TestDeleteTaskUseCase:
    def test_soft_delete(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="Duplicate")
        uc = DeleteTaskUseCase(task_repo)
        assert uc.execute(task.id, "work") is True
        assert task_repo.get_work_task(task.id) is None


class TestUpdateTaskUseCase:
    def test_update_fields(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="Original")
        uc = UpdateTaskUseCase(task_repo)
        updated = uc.execute(
            task.id,
            "work",
            title="Updated",
            status="in_progress",
        )
        assert updated.title == "Updated"
        assert updated.status == WorkTaskStatus.IN_PROGRESS


class TestBatchUpdateTasksUseCase:
    def test_batch_update(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        t1 = create.execute("work", title="Task 1")
        t2 = create.execute("personal", title="Task 2", tier=1)
        uc = BatchUpdateTasksUseCase(task_repo)
        results = uc.execute(
            [
                {"id": t1.id, "type": "work", "status": "in_progress"},
                {"id": t2.id, "type": "personal", "status": "in_progress"},
            ]
        )
        assert results[0].status == "in_progress"
        assert results[1].status == "in_progress"


class TestGetOpenTasksUseCase:
    def test_filter_by_type(self, task_repo):
        create = CreateTaskUseCase(task_repo)
        create.execute("work", title="Work task")
        create.execute("personal", title="Personal task", tier=1)
        uc = GetOpenTasksUseCase(task_repo)

        work_only = uc.execute("work")
        assert "work" in work_only
        assert "personal" not in work_only

        all_tasks = uc.execute("all")
        assert len(all_tasks["work"]) == 1
        assert len(all_tasks["personal"]) == 1


class TestGetSprintTasksUseCase:
    def test_sprint_tasks(self, task_repo, time_entry_repo, sprint_repo):
        sprint_repo.create_or_update(
            SprintEntity(
                id="2026-03-03",
                start_date=date(2026, 2, 18),
                end_date=date(2026, 3, 3),
            )
        )
        create = CreateTaskUseCase(task_repo)
        task = create.execute("work", title="Sprint task", sprint_id="2026-03-03")
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date.today(),
                duration_minutes=60,
                jn_bucket=JnBucket.DEVELOPMENT,
            )
        )
        uc = GetSprintTasksUseCase(task_repo, time_entry_repo, sprint_repo)
        tasks = uc.execute()
        assert len(tasks) == 1
        assert tasks[0].actual_hours == 1.0


class TestSetActiveSprintUseCase:
    def test_create_and_activate(self, sprint_repo):
        uc = SetActiveSprintUseCase(sprint_repo)
        sprint = uc.execute(
            "2026-03-17",
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 17),
        )
        assert sprint.status == "active"
        assert sprint_repo.get_active().id == "2026-03-17"

    def test_deactivates_previous(self, sprint_repo):
        uc = SetActiveSprintUseCase(sprint_repo)
        uc.execute(
            "2026-03-03",
            start_date=date(2026, 2, 18),
            end_date=date(2026, 3, 3),
        )
        uc.execute(
            "2026-03-17",
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 17),
        )
        assert sprint_repo.get_active().id == "2026-03-17"
        assert sprint_repo.get("2026-03-03").status == "completed"


class TestGetTrackerDataUseCase:
    def test_returns_all_sections(
        self,
        task_repo,
        time_entry_repo,
        sprint_repo,
        daily_log_repo,
        system_meta_repo,
    ):
        create = CreateTaskUseCase(task_repo)
        create.execute("work", title="Work task")
        create.execute("personal", title="Personal task", tier=1)

        uc = GetTrackerDataUseCase(
            task_repo,
            time_entry_repo,
            sprint_repo,
            daily_log_repo,
            system_meta_repo,
        )
        data = uc.execute()
        assert "work" in data
        assert "personal" in data
        assert "sprint" in data
        assert "daily_log" in data
        assert "tier3_review_due" in data
        assert data["tier3_review_due"] is True  # Never reviewed

    def test_tier3_review_not_due(
        self,
        task_repo,
        time_entry_repo,
        sprint_repo,
        daily_log_repo,
        system_meta_repo,
    ):
        system_meta_repo.set("last_tier3_review", str(date.today()))
        uc = GetTrackerDataUseCase(
            task_repo,
            time_entry_repo,
            sprint_repo,
            daily_log_repo,
            system_meta_repo,
        )
        data = uc.execute()
        assert data["tier3_review_due"] is False

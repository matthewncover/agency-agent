from datetime import date

from task_tracker.domain.entities import (
    CommitmentLevel,
    DailyLogEntity,
    JnBucket,
    PersonalTaskEntity,
    SprintEntity,
    SprintStatus,
    TimeEntryEntity,
    WorkTaskEntity,
    WorkTaskStatus,
)


class TestSqliteTaskRepositoryAdapter:
    def test_create_and_get_work_task(self, task_repo):
        task = WorkTaskEntity(
            title="Build feature",
            ods_ticket="ODS-1234",
            jn_bucket=JnBucket.DEVELOPMENT,
        )
        created = task_repo.create_work_task(task)
        assert created.id is not None
        assert created.title == "Build feature"
        assert created.created_at is not None

        fetched = task_repo.get_work_task(created.id)
        assert fetched.title == "Build feature"
        assert fetched.ods_ticket == "ODS-1234"

    def test_create_and_get_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="Buy groceries", tier=2)
        created = task_repo.create_personal_task(task)
        assert created.id is not None
        assert created.tier == 2

    def test_update_work_task(self, task_repo):
        task = WorkTaskEntity(title="Original")
        created = task_repo.create_work_task(task)
        updated = task_repo.update_work_task(
            created.id, {"title": "Updated", "status": "in_progress"}
        )
        assert updated.title == "Updated"
        assert updated.status == WorkTaskStatus.IN_PROGRESS

    def test_update_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="Original", tier=1)
        created = task_repo.create_personal_task(task)
        updated = task_repo.update_personal_task(created.id, {"pinned": True})
        assert updated.pinned is True

    def test_soft_delete_work_task(self, task_repo):
        task = WorkTaskEntity(title="To delete")
        created = task_repo.create_work_task(task)
        assert task_repo.soft_delete_work_task(created.id) is True
        assert task_repo.get_work_task(created.id) is None

    def test_soft_delete_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="To delete")
        created = task_repo.create_personal_task(task)
        assert task_repo.soft_delete_personal_task(created.id) is True
        assert task_repo.get_personal_task(created.id) is None

    def test_get_open_work_tasks(self, task_repo):
        task_repo.create_work_task(WorkTaskEntity(title="Open"))
        task_repo.create_work_task(
            WorkTaskEntity(title="Done", status=WorkTaskStatus.DONE)
        )
        open_tasks = task_repo.get_open_work_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0].title == "Open"
        # Notes stripped in list view
        assert open_tasks[0].notes is None

    def test_get_open_personal_tasks(self, task_repo):
        task_repo.create_personal_task(PersonalTaskEntity(title="Open", tier=1))
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Nuked", status="nuked")
        )
        open_tasks = task_repo.get_open_personal_tasks()
        assert len(open_tasks) == 1

    def test_work_task_children(self, task_repo):
        parent = task_repo.create_work_task(WorkTaskEntity(title="Parent task"))
        task_repo.create_work_task(
            WorkTaskEntity(title="Child 1", parent_task_id=parent.id)
        )
        task_repo.create_work_task(
            WorkTaskEntity(title="Child 2", parent_task_id=parent.id)
        )
        fetched = task_repo.get_work_task(parent.id)
        assert len(fetched.children) == 2

        # Children should not appear as top-level items
        open_tasks = task_repo.get_open_work_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0].title == "Parent task"
        assert len(open_tasks[0].children) == 2

    def test_get_sprint_tasks(self, task_repo, sprint_repo):
        sprint_repo.create_or_update(
            SprintEntity(
                id="2026-03-03",
                start_date=date(2026, 2, 18),
                end_date=date(2026, 3, 3),
            )
        )
        task_repo.create_work_task(
            WorkTaskEntity(
                title="Sprint task",
                sprint_id="2026-03-03",
                commitment_level=CommitmentLevel.SPRINT_COMMITTED,
            )
        )
        task_repo.create_work_task(
            WorkTaskEntity(
                title="Done sprint task",
                sprint_id="2026-03-03",
                status=WorkTaskStatus.DONE,
            )
        )
        task_repo.create_work_task(WorkTaskEntity(title="No sprint"))
        sprint_tasks = task_repo.get_sprint_tasks("2026-03-03")
        assert len(sprint_tasks) == 2  # Includes done tasks

    def test_get_tasks_updated_on(self, task_repo):
        task_repo.create_work_task(WorkTaskEntity(title="Today task"))
        result = task_repo.get_tasks_updated_on(date.today())
        assert len(result["work"]) == 1
        assert result["work"][0].title == "Today task"


class TestSqliteTimeEntryRepositoryAdapter:
    def test_create_and_get(self, task_repo, time_entry_repo):
        task = task_repo.create_work_task(WorkTaskEntity(title="Task"))
        entry = time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date.today(),
                duration_minutes=90,
                jn_bucket=JnBucket.DEVELOPMENT,
                notes="Worked on feature",
            )
        )
        assert entry.id is not None
        assert entry.duration_minutes == 90

    def test_get_actual_hours(self, task_repo, time_entry_repo):
        task = task_repo.create_work_task(WorkTaskEntity(title="Task"))
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date.today(),
                duration_minutes=90,
                jn_bucket=JnBucket.DEVELOPMENT,
            )
        )
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date.today(),
                duration_minutes=30,
                jn_bucket=JnBucket.PLANNING,
            )
        )
        hours = time_entry_repo.get_actual_hours(task.id)
        assert hours == 2.0

    def test_get_timecard(self, task_repo, time_entry_repo):
        task = task_repo.create_work_task(
            WorkTaskEntity(title="Task", ods_ticket="ODS-100")
        )
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date(2026, 3, 1),
                duration_minutes=120,
                jn_bucket=JnBucket.DEVELOPMENT,
            )
        )
        tc = time_entry_repo.get_timecard(date(2026, 3, 1), date(2026, 3, 1))
        assert len(tc) == 1
        assert tc[0]["total_hours"] == 2.0
        assert "ODS-100" in tc[0]["ods_tickets"]

    def test_get_time_gaps(self, task_repo, time_entry_repo):
        task = task_repo.create_work_task(WorkTaskEntity(title="Task"))
        # March 2, 2026 is a Monday
        time_entry_repo.create(
            TimeEntryEntity(
                work_task_id=task.id,
                date=date(2026, 3, 2),
                duration_minutes=360,
                jn_bucket=JnBucket.DEVELOPMENT,
            )
        )
        gaps = time_entry_repo.get_time_gaps(date(2026, 3, 2), date(2026, 3, 3))
        assert len(gaps) == 2  # Mon + Tue (weekdays)
        assert gaps[0]["gap_minutes"] == 120  # 480 - 360
        assert gaps[1]["gap_minutes"] == 480  # No time logged


class TestSqliteSprintRepositoryAdapter:
    def test_create_and_get(self, sprint_repo):
        sprint = SprintEntity(
            id="2026-03-03",
            start_date=date(2026, 2, 18),
            end_date=date(2026, 3, 3),
        )
        created = sprint_repo.create_or_update(sprint)
        assert created.id == "2026-03-03"
        assert created.status == SprintStatus.ACTIVE

    def test_get_active(self, sprint_repo):
        sprint_repo.create_or_update(
            SprintEntity(
                id="2026-03-03",
                start_date=date(2026, 2, 18),
                end_date=date(2026, 3, 3),
            )
        )
        active = sprint_repo.get_active()
        assert active.id == "2026-03-03"

    def test_deactivate_all(self, sprint_repo):
        sprint_repo.create_or_update(
            SprintEntity(
                id="2026-03-03",
                start_date=date(2026, 2, 18),
                end_date=date(2026, 3, 3),
            )
        )
        sprint_repo.deactivate_all()
        assert sprint_repo.get_active() is None


class TestSqliteDailyLogRepositoryAdapter:
    def test_create_and_get(self, daily_log_repo):
        log = DailyLogEntity(
            date=date(2026, 3, 1),
            whoop_recovery=72,
            whoop_hrv=45,
        )
        created = daily_log_repo.create_or_update(log)
        assert created.whoop_recovery == 72

        fetched = daily_log_repo.get(date(2026, 3, 1))
        assert fetched.whoop_hrv == 45

    def test_update_reflection(self, daily_log_repo):
        daily_log_repo.create_or_update(DailyLogEntity(date=date(2026, 3, 1)))
        updated = daily_log_repo.update_reflection(
            date(2026, 3, 1),
            {
                "moved_forward": "Shipped the feature",
                "observations": "Good momentum streak",
            },
        )
        assert updated.reflection_moved_forward == "Shipped the feature"
        assert updated.observations == "Good momentum streak"

    def test_update_reflection_creates_if_missing(self, daily_log_repo):
        updated = daily_log_repo.update_reflection(
            date(2026, 3, 2),
            {"moved_forward": "Started new project"},
        )
        assert updated.reflection_moved_forward == "Started new project"

    def test_get_range(self, daily_log_repo):
        daily_log_repo.create_or_update(
            DailyLogEntity(date=date(2026, 3, 1), whoop_recovery=70)
        )
        daily_log_repo.create_or_update(
            DailyLogEntity(date=date(2026, 3, 2), whoop_recovery=80)
        )
        logs = daily_log_repo.get_range(date(2026, 3, 1), date(2026, 3, 3))
        assert len(logs) == 2


class TestSqliteSystemMetaRepositoryAdapter:
    def test_set_and_get(self, system_meta_repo):
        meta = system_meta_repo.set("last_tier3_review", "2026-01-15")
        assert meta.value == "2026-01-15"

        fetched = system_meta_repo.get("last_tier3_review")
        assert fetched.value == "2026-01-15"

    def test_get_missing(self, system_meta_repo):
        assert system_meta_repo.get("nonexistent") is None

    def test_upsert(self, system_meta_repo):
        system_meta_repo.set("last_tier3_review", "2026-01-15")
        system_meta_repo.set("last_tier3_review", "2026-03-01")
        fetched = system_meta_repo.get("last_tier3_review")
        assert fetched.value == "2026-03-01"

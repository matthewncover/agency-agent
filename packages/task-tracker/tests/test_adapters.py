from datetime import date

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    PersonalTaskStatus,
)


class TestPgTaskRepositoryAdapter:
    def test_create_and_get_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="Buy groceries", tier=2)
        created = task_repo.create_personal_task(task)
        assert created.id is not None
        assert created.tier == 2
        assert created.created_at is not None

        fetched = task_repo.get_personal_task(created.id)
        assert fetched.title == "Buy groceries"

    def test_update_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="Original", tier=1)
        created = task_repo.create_personal_task(task)
        updated = task_repo.update_personal_task(
            created.id, {"title": "Updated", "status": "in_progress"}
        )
        assert updated.title == "Updated"
        assert updated.status == PersonalTaskStatus.IN_PROGRESS

    def test_update_pinned(self, task_repo):
        task = PersonalTaskEntity(title="Original", tier=3)
        created = task_repo.create_personal_task(task)
        updated = task_repo.update_personal_task(created.id, {"pinned": True})
        assert updated.pinned is True

    def test_soft_delete_personal_task(self, task_repo):
        task = PersonalTaskEntity(title="To delete")
        created = task_repo.create_personal_task(task)
        assert task_repo.soft_delete_personal_task(created.id) is True
        assert task_repo.get_personal_task(created.id) is None

    def test_get_open_personal_tasks(self, task_repo):
        task_repo.create_personal_task(PersonalTaskEntity(title="Open", tier=1))
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Nuked", status="nuked")
        )
        open_tasks = task_repo.get_open_personal_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0].title == "Open"
        # Notes stripped in list view
        assert open_tasks[0].notes is None

    def test_personal_task_children(self, task_repo):
        parent = task_repo.create_personal_task(
            PersonalTaskEntity(title="Parent task", tier=2)
        )
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Child 1", parent_task_id=parent.id)
        )
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Child 2", parent_task_id=parent.id)
        )
        fetched = task_repo.get_personal_task(parent.id)
        assert len(fetched.children) == 2

        # Children should not appear as top-level items
        open_tasks = task_repo.get_open_personal_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0].title == "Parent task"
        assert len(open_tasks[0].children) == 2

    def test_get_tasks_updated_on(self, task_repo):
        task_repo.create_personal_task(PersonalTaskEntity(title="Today task"))
        result = task_repo.get_tasks_updated_on(date.today())
        assert len(result) == 1
        assert result[0].title == "Today task"


class TestPgDailyLogRepositoryAdapter:
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


class TestPgSystemMetaRepositoryAdapter:
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


def test_search_tasks_is_case_insensitive(task_repo):
    # Regression: the PG adapter used LIKE (case-sensitive), silently diverging
    # from SQLite's case-insensitive LIKE — "vehicle" missed "Vehicle ...".
    task_repo.create_personal_task(
        PersonalTaskEntity(title="Vehicle Registration Transfer", tier=1)
    )
    for query in ("vehicle", "VEHICLE", "Vehicle registration"):
        results = task_repo.search_tasks(query)
        assert any(r["title"] == "Vehicle Registration Transfer" for r in results), (
            f"query {query!r} failed to match"
        )

from types import SimpleNamespace

import pytest

from task_tracker.server import create_app


@pytest.fixture
def tools_env(migrated_engine, person_id):
    """Fresh MCP app wired to the migrated Postgres DB for a seeded person."""
    _app, tools = create_app(engine=migrated_engine, owner_id=person_id)
    return SimpleNamespace(**tools)


class TestCreateTaskTool:
    def test_create_task(self, tools_env):
        result = tools_env.create_task(title="Buy groceries", tier=2)
        assert result["id"] is not None
        assert result["tier"] == 2
        assert result["private"] is False

    def test_create_private_task(self, tools_env):
        result = tools_env.create_task(title="Plan surprise", tier=2, private=True)
        assert result["private"] is True

    def test_update_task_toggles_private(self, tools_env):
        created = tools_env.create_task(title="Gift", tier=2)
        updated = tools_env.update_task(id=created["id"], private=True)
        assert updated["private"] is True
        updated = tools_env.update_task(id=created["id"], private=False)
        assert updated["private"] is False

    def test_create_with_deadline(self, tools_env):
        result = tools_env.create_task(title="Due Friday", deadline="2026-03-06")
        assert result["deadline"] == "2026-03-06"


class TestCreateTasksTool:
    def test_batch_create(self, tools_env):
        results = tools_env.create_tasks(
            [
                {"title": "Task A", "tier": 2},
                {"title": "Task B", "tier": 1},
            ]
        )
        assert len(results) == 2

    def test_legacy_type_key_tolerated(self, tools_env):
        results = tools_env.create_tasks(
            [{"type": "personal", "title": "Old habit", "tier": 2}]
        )
        assert results[0]["title"] == "Old habit"


class TestGetTaskDetailTool:
    def test_get_detail(self, tools_env):
        created = tools_env.create_task(title="Project X", notes="Rich context here")
        detail = tools_env.get_task_detail(id=created["id"])
        assert detail["notes"] == "Rich context here"


class TestUpdateTaskTool:
    def test_update(self, tools_env):
        created = tools_env.create_task(title="Original")
        updated = tools_env.update_task(
            id=created["id"],
            title="Updated",
            status="in_progress",
        )
        assert updated["title"] == "Updated"
        assert updated["status"] == "in_progress"


class TestRestoreTaskTool:
    def test_restore_deleted(self, tools_env):
        created = tools_env.create_task(title="Oops", tier=1)
        tools_env.delete_task(id=created["id"])
        assert tools_env.get_open_tasks() == []
        restored = tools_env.restore_task(id=created["id"])
        assert restored["id"] == created["id"]
        assert restored["deleted_at"] is None
        assert len(tools_env.get_open_tasks()) == 1

    def test_restore_non_deleted_is_noop(self, tools_env):
        created = tools_env.create_task(title="Live", tier=1)
        result = tools_env.restore_task(id=created["id"])
        assert result["id"] == created["id"]
        assert result["deleted_at"] is None

    def test_restore_missing_returns_none(self, tools_env):
        assert tools_env.restore_task(id=9999) is None


class TestSearchTasksTool:
    def test_title_match(self, tools_env):
        tools_env.create_task(title="Renew passport", tier=1)
        tools_env.create_task(title="Buy milk", tier=2)
        results = tools_env.search_tasks(query="passport")
        assert len(results) == 1
        assert results[0]["title"] == "Renew passport"

    def test_notes_match(self, tools_env):
        tools_env.create_task(
            title="Generic task", notes="involves the bronco registration"
        )
        results = tools_env.search_tasks(query="bronco")
        assert len(results) == 1

    def test_title_ranks_above_notes(self, tools_env):
        tools_env.create_task(title="Notes only", notes="alpha keyword")
        tools_env.create_task(title="alpha in title")
        results = tools_env.search_tasks(query="alpha")
        assert results[0]["title"] == "alpha in title"

    def test_excludes_done_by_default(self, tools_env):
        t = tools_env.create_task(title="done thing")
        tools_env.complete_task(id=t["id"])
        assert tools_env.search_tasks(query="done thing") == []
        assert len(tools_env.search_tasks(query="done thing", include_done=True)) == 1

    def test_excludes_deleted_by_default(self, tools_env):
        t = tools_env.create_task(title="deleted thing")
        tools_env.delete_task(id=t["id"])
        assert tools_env.search_tasks(query="deleted thing") == []
        widened = tools_env.search_tasks(query="deleted thing", include_deleted=True)
        assert len(widened) == 1

    def test_limit(self, tools_env):
        for i in range(5):
            tools_env.create_task(title=f"widget {i}")
        results = tools_env.search_tasks(query="widget", limit=2)
        assert len(results) == 2


class TestGetTimeTool:
    def test_defaults_to_pacific(self, tools_env):
        result = tools_env.get_time()
        assert result["timezone"] == "America/Los_Angeles"

    def test_override(self, tools_env):
        result = tools_env.get_time(timezone="UTC")
        assert result["timezone"] == "UTC"


class TestCompleteTaskTool:
    def test_complete(self, tools_env):
        created = tools_env.create_task(title="To finish")
        result = tools_env.complete_task(id=created["id"])
        assert result["status"] == "done"
        assert result["completed_at"] is not None


class TestNukeTaskTool:
    def test_nuke(self, tools_env):
        created = tools_env.create_task(title="To drop")
        result = tools_env.nuke_task(id=created["id"])
        assert result["status"] == "nuked"


class TestDeleteTaskTool:
    def test_delete(self, tools_env):
        created = tools_env.create_task(title="Mistake")
        result = tools_env.delete_task(id=created["id"])
        assert result["deleted"] is True


class TestGetOpenTasksTool:
    def test_get_open(self, tools_env):
        tools_env.create_task(title="Open item", tier=1)
        done = tools_env.create_task(title="Done item", tier=1)
        tools_env.complete_task(id=done["id"])
        result = tools_env.get_open_tasks()
        assert [t["title"] for t in result] == ["Open item"]


class TestGetTasksUpdatedOnTool:
    def test_updated_today(self, tools_env):
        from datetime import date

        tools_env.create_task(title="Touched today", tier=2)
        result = tools_env.get_tasks_updated_on(target_date=str(date.today()))
        assert [t["title"] for t in result] == ["Touched today"]


class TestGetTrackerDataTool:
    def test_tracker_data(self, tools_env):
        tools_env.create_task(title="Personal item", tier=2)
        data = tools_env.get_tracker_data()
        assert "personal" in data
        assert "daily_log" in data
        assert "tier3_review_due" in data
        assert "work" not in data
        assert "sprint" not in data


class TestDailyLogTools:
    def test_log_daily(self, tools_env):
        result = tools_env.log_daily(
            target_date="2026-03-01",
            whoop_recovery=72,
            whoop_hrv=45,
        )
        assert result["whoop_recovery"] == 72

    def test_log_reflection(self, tools_env):
        tools_env.log_daily(target_date="2026-03-01")
        result = tools_env.log_reflection(
            target_date="2026-03-01",
            moved_forward="Shipped the feature",
            observations="Strong momentum",
        )
        assert result["reflection_moved_forward"] == "Shipped the feature"
        assert result["observations"] == "Strong momentum"

    def test_get_daily_log(self, tools_env):
        tools_env.log_daily(target_date="2026-03-01", whoop_recovery=80)
        result = tools_env.get_daily_log(target_date="2026-03-01")
        assert result["whoop_recovery"] == 80

    def test_get_daily_logs(self, tools_env):
        tools_env.log_daily(target_date="2026-03-01", whoop_recovery=70)
        tools_env.log_daily(target_date="2026-03-02", whoop_recovery=80)
        results = tools_env.get_daily_logs(
            start_date="2026-03-01", end_date="2026-03-02"
        )
        assert len(results) == 2


class TestSetMetaTool:
    def test_set_meta(self, tools_env):
        result = tools_env.set_meta(key="last_tier3_review", value="2026-03-01")
        assert result["value"] == "2026-03-01"


class TestBatchUpdateTasksTool:
    def test_batch_update(self, tools_env):
        t1 = tools_env.create_task(title="Task 1", tier=1)
        t2 = tools_env.create_task(title="Task 2", tier=2)
        results = tools_env.batch_update_tasks(
            [
                {"id": t1["id"], "status": "in_progress"},
                {"id": t2["id"], "status": "in_progress"},
            ]
        )
        assert results[0]["status"] == "in_progress"
        assert results[1]["status"] == "in_progress"


class TestRemovedWorkSurface:
    def test_work_tools_gone(self, tools_env):
        for name in (
            "log_time",
            "delete_time_entry",
            "get_timecard",
            "get_time_gaps",
            "set_active_sprint",
            "get_sprint_tasks",
            "get_estimation_accuracy",
        ):
            assert not hasattr(tools_env, name)

from types import SimpleNamespace

import pytest

from task_tracker.server import create_app


@pytest.fixture
def tools_env(migrated_engine, person_id):
    """Fresh MCP app wired to the migrated Postgres DB for a seeded person."""
    _app, tools = create_app(engine=migrated_engine, owner_id=person_id)
    return SimpleNamespace(**tools)


class TestCreateTaskTool:
    def test_create_work_task(self, tools_env):
        result = tools_env.create_task(
            type="work",
            title="Build feature",
            jn_bucket="development",
        )
        assert result["id"] is not None
        assert result["title"] == "Build feature"
        assert result["jn_bucket"] == "development"

    def test_create_personal_task(self, tools_env):
        result = tools_env.create_task(
            type="personal",
            title="Buy groceries",
            tier=2,
        )
        assert result["id"] is not None
        assert result["tier"] == 2

    def test_create_with_deadline(self, tools_env):
        result = tools_env.create_task(
            type="work",
            title="Due Friday",
            deadline="2026-03-06",
        )
        assert result["deadline"] == "2026-03-06"


class TestCreateTasksTool:
    def test_batch_create(self, tools_env):
        results = tools_env.create_tasks(
            [
                {"type": "work", "title": "Task A"},
                {"type": "personal", "title": "Task B", "tier": 1},
            ]
        )
        assert len(results) == 2


class TestGetTaskDetailTool:
    def test_get_detail(self, tools_env):
        created = tools_env.create_task(
            type="work",
            title="Feature X",
            notes="Rich context here",
        )
        detail = tools_env.get_task_detail(id=created["id"], type="work")
        assert detail["notes"] == "Rich context here"
        assert detail["actual_hours"] is not None


class TestUpdateTaskTool:
    def test_update(self, tools_env):
        created = tools_env.create_task(type="work", title="Original")
        updated = tools_env.update_task(
            id=created["id"],
            type="work",
            title="Updated",
            status="in_progress",
        )
        assert updated["title"] == "Updated"
        assert updated["status"] == "in_progress"


class TestUpdateTaskTitleTool:
    def test_update_title(self, tools_env):
        created = tools_env.create_task(type="work", title="Old title")
        updated = tools_env.update_task(
            id=created["id"], type="work", title="New title"
        )
        assert updated["title"] == "New title"

    def test_update_personal_title(self, tools_env):
        created = tools_env.create_task(type="personal", title="Old", tier=2)
        updated = tools_env.update_task(id=created["id"], type="personal", title="New")
        assert updated["title"] == "New"


class TestRestoreTaskTool:
    def test_restore_deleted(self, tools_env):
        created = tools_env.create_task(type="work", title="Oops")
        tools_env.delete_task(id=created["id"], type="work")
        assert tools_env.get_open_tasks(type="work")["work"] == []
        restored = tools_env.restore_task(id=created["id"], type="work")
        assert restored["id"] == created["id"]
        assert restored["deleted_at"] is None
        assert len(tools_env.get_open_tasks(type="work")["work"]) == 1

    def test_restore_non_deleted_is_noop(self, tools_env):
        created = tools_env.create_task(type="personal", title="Live", tier=1)
        result = tools_env.restore_task(id=created["id"], type="personal")
        assert result["id"] == created["id"]
        assert result["deleted_at"] is None

    def test_restore_missing_returns_none(self, tools_env):
        assert tools_env.restore_task(id=9999, type="work") is None


class TestDeleteTimeEntryTool:
    def test_delete_returns_row(self, tools_env):
        task = tools_env.create_task(type="work", title="Work")
        entry = tools_env.log_time(
            work_task_id=task["id"],
            target_date="2026-03-01",
            duration_minutes=45,
            jn_bucket="development",
            notes="wrong chat",
        )
        deleted = tools_env.delete_time_entry(time_entry_id=entry["id"])
        assert deleted["id"] == entry["id"]
        assert deleted["duration_minutes"] == 45
        assert deleted["notes"] == "wrong chat"
        # Gone for good — actual_hours back to zero
        detail = tools_env.get_task_detail(id=task["id"], type="work")
        assert detail["actual_hours"] == 0

    def test_delete_missing_returns_none(self, tools_env):
        assert tools_env.delete_time_entry(time_entry_id=9999) is None


class TestSearchTasksTool:
    def test_title_match(self, tools_env):
        tools_env.create_task(type="work", title="Fix login bug")
        tools_env.create_task(type="personal", title="Buy milk", tier=2)
        results = tools_env.search_tasks(query="login")
        assert len(results) == 1
        assert results[0]["title"] == "Fix login bug"
        assert results[0]["type"] == "work"

    def test_notes_match(self, tools_env):
        tools_env.create_task(
            type="work", title="Generic task", notes="involves the bronco registration"
        )
        results = tools_env.search_tasks(query="bronco")
        assert len(results) == 1

    def test_title_ranks_above_notes(self, tools_env):
        tools_env.create_task(type="work", title="Notes only", notes="alpha keyword")
        tools_env.create_task(type="work", title="alpha in title")
        results = tools_env.search_tasks(query="alpha")
        assert results[0]["title"] == "alpha in title"

    def test_excludes_done_by_default(self, tools_env):
        t = tools_env.create_task(type="work", title="done thing")
        tools_env.complete_task(id=t["id"], type="work")
        assert tools_env.search_tasks(query="done thing") == []
        assert len(tools_env.search_tasks(query="done thing", include_done=True)) == 1

    def test_excludes_deleted_by_default(self, tools_env):
        t = tools_env.create_task(type="work", title="deleted thing")
        tools_env.delete_task(id=t["id"], type="work")
        assert tools_env.search_tasks(query="deleted thing") == []
        widened = tools_env.search_tasks(query="deleted thing", include_deleted=True)
        assert len(widened) == 1

    def test_limit(self, tools_env):
        for i in range(5):
            tools_env.create_task(type="work", title=f"widget {i}")
        results = tools_env.search_tasks(query="widget", limit=2)
        assert len(results) == 2


class TestGetEstimationAccuracyTool:
    def test_accuracy(self, tools_env):
        t = tools_env.create_task(
            type="work", title="Estimated task", estimate_hours=2.0
        )
        tools_env.log_time(
            work_task_id=t["id"],
            target_date="2026-03-01",
            duration_minutes=180,
            jn_bucket="development",
        )
        tools_env.complete_task(id=t["id"], type="work")
        result = tools_env.get_estimation_accuracy()
        assert len(result["tasks"]) == 1
        row = result["tasks"][0]
        assert row["estimate_hours"] == 2.0
        assert row["actual_hours"] == 3.0
        assert row["ratio"] == 1.5
        assert result["median_ratio"] == 1.5

    def test_ignores_open_and_estimateless(self, tools_env):
        tools_env.create_task(type="work", title="Open", estimate_hours=2.0)
        done = tools_env.create_task(type="work", title="No estimate")
        tools_env.complete_task(id=done["id"], type="work")
        result = tools_env.get_estimation_accuracy()
        assert result["tasks"] == []
        assert result["median_ratio"] is None

    def test_personal_type_returns_empty(self, tools_env):
        result = tools_env.get_estimation_accuracy(type="personal")
        assert result["tasks"] == []


class TestGetTimeTool:
    def test_defaults_to_pacific(self, tools_env):
        result = tools_env.get_time()
        assert result["timezone"] == "America/Los_Angeles"

    def test_override(self, tools_env):
        result = tools_env.get_time(timezone="UTC")
        assert result["timezone"] == "UTC"


class TestCompleteTaskTool:
    def test_complete(self, tools_env):
        created = tools_env.create_task(type="work", title="To finish")
        result = tools_env.complete_task(id=created["id"], type="work")
        assert result["status"] == "done"
        assert result["completed_at"] is not None


class TestNukeTaskTool:
    def test_nuke(self, tools_env):
        created = tools_env.create_task(type="work", title="To drop")
        result = tools_env.nuke_task(id=created["id"], type="work")
        assert result["status"] == "nuked"


class TestDeleteTaskTool:
    def test_delete(self, tools_env):
        created = tools_env.create_task(type="work", title="Mistake")
        result = tools_env.delete_task(id=created["id"], type="work")
        assert result["deleted"] is True


class TestGetOpenTasksTool:
    def test_get_open(self, tools_env):
        tools_env.create_task(type="work", title="Open work")
        tools_env.create_task(type="personal", title="Open personal", tier=1)
        result = tools_env.get_open_tasks(type="all")
        assert len(result["work"]) == 1
        assert len(result["personal"]) == 1


class TestGetTrackerDataTool:
    def test_tracker_data(self, tools_env):
        tools_env.create_task(type="work", title="Work item")
        tools_env.create_task(type="personal", title="Personal item", tier=2)
        data = tools_env.get_tracker_data()
        assert "work" in data
        assert "personal" in data
        assert "sprint" in data
        assert "daily_log" in data
        assert "tier3_review_due" in data


class TestLogTimeTool:
    def test_log_time(self, tools_env):
        task = tools_env.create_task(type="work", title="Work")
        entry = tools_env.log_time(
            work_task_id=task["id"],
            target_date="2026-03-01",
            duration_minutes=90,
            jn_bucket="development",
            notes="Coded feature",
        )
        assert entry["duration_minutes"] == 90
        assert entry["jn_bucket"] == "development"


class TestGetTimecardTool:
    def test_timecard(self, tools_env):
        task = tools_env.create_task(type="work", title="Work", ods_ticket="ODS-100")
        tools_env.log_time(
            work_task_id=task["id"],
            target_date="2026-03-01",
            duration_minutes=120,
            jn_bucket="development",
        )
        tc = tools_env.get_timecard(start_date="2026-03-01", end_date="2026-03-01")
        assert len(tc) == 1
        assert tc[0]["total_hours"] == 2.0


class TestGetTimeGapsTool:
    def test_gaps(self, tools_env):
        task = tools_env.create_task(type="work", title="Work")
        tools_env.log_time(
            work_task_id=task["id"],
            target_date="2026-03-02",
            duration_minutes=360,
            jn_bucket="development",
        )
        gaps = tools_env.get_time_gaps(start_date="2026-03-02", end_date="2026-03-02")
        assert len(gaps) == 1
        assert gaps[0]["gap_minutes"] == 120


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


class TestSprintManagement:
    def test_set_active_sprint(self, tools_env):
        result = tools_env.set_active_sprint(
            sprint_id="2026-03-17",
            start_date="2026-03-04",
            end_date="2026-03-17",
        )
        assert result["status"] == "active"
        assert result["id"] == "2026-03-17"

    def test_get_sprint_tasks(self, tools_env):
        tools_env.set_active_sprint(
            sprint_id="2026-03-17",
            start_date="2026-03-04",
            end_date="2026-03-17",
        )
        tools_env.create_task(
            type="work",
            title="Sprint task",
            sprint_id="2026-03-17",
        )
        tasks = tools_env.get_sprint_tasks()
        assert len(tasks) == 1


class TestSetMetaTool:
    def test_set_meta(self, tools_env):
        result = tools_env.set_meta(key="last_tier3_review", value="2026-03-01")
        assert result["value"] == "2026-03-01"


class TestBatchUpdateTasksTool:
    def test_batch_update(self, tools_env):
        t1 = tools_env.create_task(type="work", title="Task 1")
        t2 = tools_env.create_task(type="personal", title="Task 2", tier=1)
        results = tools_env.batch_update_tasks(
            [
                {
                    "id": t1["id"],
                    "type": "work",
                    "status": "in_progress",
                },
                {
                    "id": t2["id"],
                    "type": "personal",
                    "status": "in_progress",
                },
            ]
        )
        assert results[0]["status"] == "in_progress"
        assert results[1]["status"] == "in_progress"

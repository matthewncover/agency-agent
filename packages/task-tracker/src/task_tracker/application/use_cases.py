from datetime import date, datetime, timedelta

from task_tracker.application.ports import (
    DailyLogRepositoryPort,
    SprintRepositoryPort,
    SystemMetaRepositoryPort,
    TaskRepositoryPort,
    TimeEntryRepositoryPort,
)
from task_tracker.domain.entities import (
    DailyLogEntity,
    JnBucket,
    PersonalTaskEntity,
    SprintEntity,
    SprintStatus,
    SystemMetaEntity,
    TimeEntryEntity,
    WorkTaskEntity,
)
from task_tracker.domain.factories import PersonalTaskFactory, WorkTaskFactory


class CreateTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_type: str, **fields) -> WorkTaskEntity | PersonalTaskEntity:
        if task_type == "work":
            task = WorkTaskFactory.create(**fields)
            return self._task_repo.create_work_task(task)
        elif task_type == "personal":
            task = PersonalTaskFactory.create(**fields)
            return self._task_repo.create_personal_task(task)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class CreateTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, tasks: list[dict]) -> list[WorkTaskEntity | PersonalTaskEntity]:
        results = []
        create = CreateTaskUseCase(self._task_repo)
        for task_data in tasks:
            task_type = task_data.pop("type")
            results.append(create.execute(task_type, **task_data))
        return results


class GetTaskDetailUseCase:
    def __init__(
        self,
        task_repo: TaskRepositoryPort,
        time_entry_repo: TimeEntryRepositoryPort,
    ):
        self._task_repo = task_repo
        self._time_entry_repo = time_entry_repo

    def execute(
        self, task_id: int, task_type: str
    ) -> WorkTaskEntity | PersonalTaskEntity | None:
        if task_type == "work":
            task = self._task_repo.get_work_task(task_id)
            if task:
                task.actual_hours = self._time_entry_repo.get_actual_hours(task_id)
                self._compute_days_carried(task)
                for child in task.children:
                    child.actual_hours = self._time_entry_repo.get_actual_hours(
                        child.id
                    )
                    self._compute_days_carried(child)
            return task
        elif task_type == "personal":
            task = self._task_repo.get_personal_task(task_id)
            if task:
                self._compute_days_carried(task)
                for child in task.children:
                    self._compute_days_carried(child)
            return task
        else:
            raise ValueError(f"Invalid task type: {task_type}")

    @staticmethod
    def _compute_days_carried(
        task: WorkTaskEntity | PersonalTaskEntity,
    ) -> None:
        if task.created_at and task.status not in ("done", "nuked"):
            delta = datetime.now() - task.created_at
            task.days_carried = delta.days
        else:
            task.days_carried = None


class UpdateTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self, task_id: int, task_type: str, **fields
    ) -> WorkTaskEntity | PersonalTaskEntity | None:
        if task_type == "work":
            return self._task_repo.update_work_task(task_id, fields)
        elif task_type == "personal":
            return self._task_repo.update_personal_task(task_id, fields)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class BatchUpdateTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self, updates: list[dict]
    ) -> list[WorkTaskEntity | PersonalTaskEntity | None]:
        results = []
        update = UpdateTaskUseCase(self._task_repo)
        for item in updates:
            task_id = item.pop("id")
            task_type = item.pop("type")
            results.append(update.execute(task_id, task_type, **item))
        return results


class CompleteTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self, task_id: int, task_type: str
    ) -> WorkTaskEntity | PersonalTaskEntity | None:
        fields = {
            "status": "done",
            "completed_at": datetime.now(),
        }
        if task_type == "work":
            return self._task_repo.update_work_task(task_id, fields)
        elif task_type == "personal":
            return self._task_repo.update_personal_task(task_id, fields)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class NukeTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self, task_id: int, task_type: str
    ) -> WorkTaskEntity | PersonalTaskEntity | None:
        fields = {"status": "nuked"}
        if task_type == "work":
            return self._task_repo.update_work_task(task_id, fields)
        elif task_type == "personal":
            return self._task_repo.update_personal_task(task_id, fields)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class DeleteTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int, task_type: str) -> bool:
        if task_type == "work":
            return self._task_repo.soft_delete_work_task(task_id)
        elif task_type == "personal":
            return self._task_repo.soft_delete_personal_task(task_id)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class RestoreTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self, task_id: int, task_type: str
    ) -> WorkTaskEntity | PersonalTaskEntity | None:
        if task_type == "work":
            return self._task_repo.restore_work_task(task_id)
        elif task_type == "personal":
            return self._task_repo.restore_personal_task(task_id)
        else:
            raise ValueError(f"Invalid task type: {task_type}")


class SearchTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self,
        query: str,
        include_done: bool = False,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        return self._task_repo.search_tasks(query, include_done, include_deleted, limit)


class GetEstimationAccuracyUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, n: int | None = None, task_type: str | None = None) -> dict:
        rows = self._task_repo.get_estimation_data(n, task_type)
        tasks = []
        ratios = []
        for row in rows:
            estimate = row["estimate_hours"]
            actual = row["actual_hours"]
            ratio = round(actual / estimate, 2) if estimate else None
            if ratio is not None:
                ratios.append(ratio)
            tasks.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "estimate_hours": estimate,
                    "actual_hours": actual,
                    "ratio": ratio,
                }
            )
        return {"tasks": tasks, "median_ratio": _median(ratios)}


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2, 2)


class GetOpenTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(
        self,
        task_type: str = "all",
        min_days_open: int | None = None,
    ) -> dict[str, list]:
        result: dict[str, list] = {}
        if task_type in ("work", "all"):
            result["work"] = self._task_repo.get_open_work_tasks(min_days_open)
        if task_type in ("personal", "all"):
            result["personal"] = self._task_repo.get_open_personal_tasks(min_days_open)
        return result


class GetSprintTasksUseCase:
    def __init__(
        self,
        task_repo: TaskRepositoryPort,
        time_entry_repo: TimeEntryRepositoryPort,
        sprint_repo: SprintRepositoryPort,
    ):
        self._task_repo = task_repo
        self._time_entry_repo = time_entry_repo
        self._sprint_repo = sprint_repo

    def execute(self, sprint_id: str | None = None) -> list[WorkTaskEntity]:
        if sprint_id is None:
            active = self._sprint_repo.get_active()
            if active is None:
                return []
            sprint_id = active.id
        tasks = self._task_repo.get_sprint_tasks(sprint_id)
        for task in tasks:
            task.actual_hours = self._time_entry_repo.get_actual_hours(task.id)
        return tasks


class GetTasksUpdatedOnUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, target_date: date) -> dict[str, list]:
        return self._task_repo.get_tasks_updated_on(target_date)


class GetTrackerDataUseCase:
    def __init__(
        self,
        task_repo: TaskRepositoryPort,
        time_entry_repo: TimeEntryRepositoryPort,
        sprint_repo: SprintRepositoryPort,
        daily_log_repo: DailyLogRepositoryPort,
        system_meta_repo: SystemMetaRepositoryPort,
    ):
        self._task_repo = task_repo
        self._time_entry_repo = time_entry_repo
        self._sprint_repo = sprint_repo
        self._daily_log_repo = daily_log_repo
        self._system_meta_repo = system_meta_repo

    def execute(self) -> dict:
        today = date.today()

        # Open work tasks with annotations
        work_tasks = self._task_repo.get_open_work_tasks()
        self._annotate_tasks(work_tasks, today)

        # Open personal tasks with annotations
        personal_tasks = self._task_repo.get_open_personal_tasks()
        self._annotate_tasks(personal_tasks, today)

        # Active sprint + sprint tasks
        active_sprint = self._sprint_repo.get_active()
        sprint_tasks = []
        if active_sprint:
            sprint_tasks = self._task_repo.get_sprint_tasks(active_sprint.id)
            for t in sprint_tasks:
                t.actual_hours = self._time_entry_repo.get_actual_hours(t.id)

        # Today's daily log
        daily_log = self._daily_log_repo.get(today)

        # Tier 3 review due
        meta = self._system_meta_repo.get("last_tier3_review")
        if meta is None:
            tier3_review_due = True
        else:
            last_review = date.fromisoformat(meta.value)
            tier3_review_due = (today - last_review).days >= 90

        return {
            "work": [t.model_dump() for t in work_tasks],
            "personal": [t.model_dump() for t in personal_tasks],
            "sprint": {
                "info": active_sprint.model_dump() if active_sprint else None,
                "tasks": [t.model_dump() for t in sprint_tasks],
            },
            "daily_log": daily_log.model_dump() if daily_log else None,
            "tier3_review_due": tier3_review_due,
        }

    @staticmethod
    def _annotate_tasks(tasks: list, today: date) -> None:
        for task in tasks:
            task.is_stale = task.days_carried is not None and task.days_carried >= 30
            task.is_blocked = task.status in ("blocked", "waiting")
            task.has_upcoming_deadline = (
                task.deadline is not None and task.deadline <= today + timedelta(days=3)
            )
            for child in task.children:
                child.is_stale = (
                    child.days_carried is not None and child.days_carried >= 30
                )
                child.is_blocked = child.status in ("blocked", "waiting")
                child.has_upcoming_deadline = (
                    child.deadline is not None
                    and child.deadline <= today + timedelta(days=3)
                )


class LogTimeUseCase:
    def __init__(self, time_entry_repo: TimeEntryRepositoryPort):
        self._time_entry_repo = time_entry_repo

    def execute(
        self,
        work_task_id: int,
        entry_date: date,
        duration_minutes: int,
        jn_bucket: JnBucket,
        notes: str | None = None,
    ) -> TimeEntryEntity:
        entry = TimeEntryEntity(
            work_task_id=work_task_id,
            date=entry_date,
            duration_minutes=duration_minutes,
            jn_bucket=jn_bucket,
            notes=notes,
        )
        return self._time_entry_repo.create(entry)


class DeleteTimeEntryUseCase:
    def __init__(self, time_entry_repo: TimeEntryRepositoryPort):
        self._time_entry_repo = time_entry_repo

    def execute(self, time_entry_id: int) -> TimeEntryEntity | None:
        return self._time_entry_repo.delete(time_entry_id)


class GetTimecardUseCase:
    def __init__(self, time_entry_repo: TimeEntryRepositoryPort):
        self._time_entry_repo = time_entry_repo

    def execute(self, start_date: date, end_date: date) -> list[dict]:
        return self._time_entry_repo.get_timecard(start_date, end_date)


class GetTimeGapsUseCase:
    def __init__(self, time_entry_repo: TimeEntryRepositoryPort):
        self._time_entry_repo = time_entry_repo

    def execute(self, start_date: date, end_date: date) -> list[dict]:
        return self._time_entry_repo.get_time_gaps(start_date, end_date)


class LogDailyUseCase:
    def __init__(self, daily_log_repo: DailyLogRepositoryPort):
        self._daily_log_repo = daily_log_repo

    def execute(
        self,
        log_date: date,
        whoop_recovery: int | None = None,
        whoop_hrv: int | None = None,
        whoop_sleep_hours: float | None = None,
        whoop_rhr: int | None = None,
        notes: str | None = None,
    ) -> DailyLogEntity:
        log = DailyLogEntity(
            date=log_date,
            whoop_recovery=whoop_recovery,
            whoop_hrv=whoop_hrv,
            whoop_sleep_hours=whoop_sleep_hours,
            whoop_rhr=whoop_rhr,
            notes=notes,
        )
        return self._daily_log_repo.create_or_update(log)


class LogReflectionUseCase:
    def __init__(self, daily_log_repo: DailyLogRepositoryPort):
        self._daily_log_repo = daily_log_repo

    def execute(self, log_date: date, **fields) -> DailyLogEntity | None:
        return self._daily_log_repo.update_reflection(log_date, fields)


class GetDailyLogUseCase:
    def __init__(self, daily_log_repo: DailyLogRepositoryPort):
        self._daily_log_repo = daily_log_repo

    def execute(self, log_date: date) -> DailyLogEntity | None:
        return self._daily_log_repo.get(log_date)


class GetDailyLogsUseCase:
    def __init__(self, daily_log_repo: DailyLogRepositoryPort):
        self._daily_log_repo = daily_log_repo

    def execute(self, start_date: date, end_date: date) -> list[DailyLogEntity]:
        return self._daily_log_repo.get_range(start_date, end_date)


class SetActiveSprintUseCase:
    def __init__(self, sprint_repo: SprintRepositoryPort):
        self._sprint_repo = sprint_repo

    def execute(
        self,
        sprint_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SprintEntity:
        existing = self._sprint_repo.get(sprint_id)
        if existing:
            self._sprint_repo.deactivate_all()
            existing.status = SprintStatus.ACTIVE
            return self._sprint_repo.create_or_update(existing)
        else:
            if start_date is None or end_date is None:
                raise ValueError("start_date and end_date required for new sprints")
            self._sprint_repo.deactivate_all()
            sprint = SprintEntity(
                id=sprint_id,
                start_date=start_date,
                end_date=end_date,
                status=SprintStatus.ACTIVE,
            )
            return self._sprint_repo.create_or_update(sprint)


class SetMetaUseCase:
    def __init__(self, system_meta_repo: SystemMetaRepositoryPort):
        self._system_meta_repo = system_meta_repo

    def execute(self, key: str, value: str) -> SystemMetaEntity:
        return self._system_meta_repo.set(key, value)

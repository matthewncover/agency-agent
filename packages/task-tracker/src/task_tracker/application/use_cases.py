from datetime import date, datetime, timedelta

from task_tracker.application.ports import (
    DailyLogRepositoryPort,
    SystemMetaRepositoryPort,
    TaskRepositoryPort,
)
from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    SystemMetaEntity,
)
from task_tracker.domain.factories import PersonalTaskFactory


class CreateTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, **fields) -> PersonalTaskEntity:
        task = PersonalTaskFactory.create(**fields)
        return self._task_repo.create_personal_task(task)


class CreateTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, tasks: list[dict]) -> list[PersonalTaskEntity]:
        create = CreateTaskUseCase(self._task_repo)
        return [create.execute(**task_data) for task_data in tasks]


class GetTaskDetailUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int) -> PersonalTaskEntity | None:
        task = self._task_repo.get_personal_task(task_id)
        if task:
            self._compute_days_carried(task)
            for child in task.children:
                self._compute_days_carried(child)
        return task

    @staticmethod
    def _compute_days_carried(task: PersonalTaskEntity) -> None:
        if task.created_at and task.status not in ("done", "nuked"):
            delta = datetime.now() - task.created_at
            task.days_carried = delta.days
        else:
            task.days_carried = None


class UpdateTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int, **fields) -> PersonalTaskEntity | None:
        return self._task_repo.update_personal_task(task_id, fields)


class BatchUpdateTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, updates: list[dict]) -> list[PersonalTaskEntity | None]:
        results = []
        update = UpdateTaskUseCase(self._task_repo)
        for item in updates:
            task_id = item.pop("id")
            results.append(update.execute(task_id, **item))
        return results


class CompleteTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int) -> PersonalTaskEntity | None:
        fields = {
            "status": "done",
            "completed_at": datetime.now(),
        }
        return self._task_repo.update_personal_task(task_id, fields)


class NukeTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int) -> PersonalTaskEntity | None:
        return self._task_repo.update_personal_task(task_id, {"status": "nuked"})


class DeleteTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int) -> bool:
        return self._task_repo.soft_delete_personal_task(task_id)


class RestoreTaskUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, task_id: int) -> PersonalTaskEntity | None:
        return self._task_repo.restore_personal_task(task_id)


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


class GetOpenTasksUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, min_days_open: int | None = None) -> list[PersonalTaskEntity]:
        return self._task_repo.get_open_personal_tasks(min_days_open)


class GetTasksUpdatedOnUseCase:
    def __init__(self, task_repo: TaskRepositoryPort):
        self._task_repo = task_repo

    def execute(self, target_date: date) -> list[PersonalTaskEntity]:
        return self._task_repo.get_tasks_updated_on(target_date)


class GetTrackerDataUseCase:
    def __init__(
        self,
        task_repo: TaskRepositoryPort,
        daily_log_repo: DailyLogRepositoryPort,
        system_meta_repo: SystemMetaRepositoryPort,
    ):
        self._task_repo = task_repo
        self._daily_log_repo = daily_log_repo
        self._system_meta_repo = system_meta_repo

    def execute(self) -> dict:
        today = date.today()

        # Open personal tasks with annotations
        personal_tasks = self._task_repo.get_open_personal_tasks()
        self._annotate_tasks(personal_tasks, today)

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
            "personal": [t.model_dump() for t in personal_tasks],
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


class SetMetaUseCase:
    def __init__(self, system_meta_repo: SystemMetaRepositoryPort):
        self._system_meta_repo = system_meta_repo

    def execute(self, key: str, value: str) -> SystemMetaEntity:
        return self._system_meta_repo.set(key, value)

from abc import ABC, abstractmethod
from datetime import date

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    SprintEntity,
    SystemMetaEntity,
    TimeEntryEntity,
    WorkTaskEntity,
)


class TaskRepositoryPort(ABC):
    @abstractmethod
    def create_work_task(self, task: WorkTaskEntity) -> WorkTaskEntity: ...

    @abstractmethod
    def create_personal_task(self, task: PersonalTaskEntity) -> PersonalTaskEntity: ...

    @abstractmethod
    def get_work_task(self, task_id: int) -> WorkTaskEntity | None: ...

    @abstractmethod
    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None: ...

    @abstractmethod
    def update_work_task(self, task_id: int, fields: dict) -> WorkTaskEntity | None: ...

    @abstractmethod
    def update_personal_task(
        self, task_id: int, fields: dict
    ) -> PersonalTaskEntity | None: ...

    @abstractmethod
    def soft_delete_work_task(self, task_id: int) -> bool: ...

    @abstractmethod
    def soft_delete_personal_task(self, task_id: int) -> bool: ...

    @abstractmethod
    def restore_work_task(self, task_id: int) -> WorkTaskEntity | None: ...

    @abstractmethod
    def restore_personal_task(self, task_id: int) -> PersonalTaskEntity | None: ...

    @abstractmethod
    def search_tasks(
        self,
        query: str,
        include_done: bool = False,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[dict]: ...

    @abstractmethod
    def get_estimation_data(
        self, n: int | None = None, task_type: str | None = None
    ) -> list[dict]: ...

    @abstractmethod
    def get_open_work_tasks(
        self, min_days_open: int | None = None
    ) -> list[WorkTaskEntity]: ...

    @abstractmethod
    def get_open_personal_tasks(
        self, min_days_open: int | None = None
    ) -> list[PersonalTaskEntity]: ...

    @abstractmethod
    def get_sprint_tasks(
        self, sprint_id: str | None = None
    ) -> list[WorkTaskEntity]: ...

    @abstractmethod
    def get_tasks_updated_on(self, target_date: date) -> dict[str, list]: ...


class TimeEntryRepositoryPort(ABC):
    @abstractmethod
    def create(self, entry: TimeEntryEntity) -> TimeEntryEntity: ...

    @abstractmethod
    def get_for_task(self, work_task_id: int) -> list[TimeEntryEntity]: ...

    @abstractmethod
    def get_timecard(self, start_date: date, end_date: date) -> list[dict]: ...

    @abstractmethod
    def get_time_gaps(self, start_date: date, end_date: date) -> list[dict]: ...

    @abstractmethod
    def get_actual_hours(self, work_task_id: int) -> float: ...

    @abstractmethod
    def delete(self, time_entry_id: int) -> TimeEntryEntity | None: ...


class SprintRepositoryPort(ABC):
    @abstractmethod
    def get(self, sprint_id: str) -> SprintEntity | None: ...

    @abstractmethod
    def get_active(self) -> SprintEntity | None: ...

    @abstractmethod
    def create_or_update(self, sprint: SprintEntity) -> SprintEntity: ...

    @abstractmethod
    def deactivate_all(self) -> None: ...


class DailyLogRepositoryPort(ABC):
    @abstractmethod
    def create_or_update(self, log: DailyLogEntity) -> DailyLogEntity: ...

    @abstractmethod
    def get(self, target_date: date) -> DailyLogEntity | None: ...

    @abstractmethod
    def get_range(self, start_date: date, end_date: date) -> list[DailyLogEntity]: ...

    @abstractmethod
    def update_reflection(
        self, target_date: date, fields: dict
    ) -> DailyLogEntity | None: ...


class SystemMetaRepositoryPort(ABC):
    @abstractmethod
    def get(self, key: str) -> SystemMetaEntity | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> SystemMetaEntity: ...

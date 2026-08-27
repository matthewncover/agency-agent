from abc import ABC, abstractmethod
from datetime import date

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    SystemMetaEntity,
)


class TaskRepositoryPort(ABC):
    @abstractmethod
    def create_personal_task(self, task: PersonalTaskEntity) -> PersonalTaskEntity: ...

    @abstractmethod
    def get_personal_task(self, task_id: int) -> PersonalTaskEntity | None: ...

    @abstractmethod
    def update_personal_task(
        self, task_id: int, fields: dict
    ) -> PersonalTaskEntity | None: ...

    @abstractmethod
    def soft_delete_personal_task(self, task_id: int) -> bool: ...

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
    def get_open_personal_tasks(
        self, min_days_open: int | None = None
    ) -> list[PersonalTaskEntity]: ...

    @abstractmethod
    def get_tasks_updated_on(self, target_date: date) -> list[PersonalTaskEntity]: ...


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

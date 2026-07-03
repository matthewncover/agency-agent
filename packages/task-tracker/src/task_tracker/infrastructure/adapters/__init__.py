from task_tracker.infrastructure.adapters.daily_log import (
    SqliteDailyLogRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_daily_log import (
    PgDailyLogRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_sprint import PgSprintRepositoryAdapter
from task_tracker.infrastructure.adapters.pg_system_meta import (
    PgSystemMetaRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_task import PgTaskRepositoryAdapter
from task_tracker.infrastructure.adapters.pg_time_entry import (
    PgTimeEntryRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.sprint import (
    SqliteSprintRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.system_meta import (
    SqliteSystemMetaRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.task import (
    SqliteTaskRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.time_entry import (
    SqliteTimeEntryRepositoryAdapter,
)

__all__ = [
    # Postgres adapters (the monorepo runtime — ADR-0008)
    "PgDailyLogRepositoryAdapter",
    "PgSprintRepositoryAdapter",
    "PgSystemMetaRepositoryAdapter",
    "PgTaskRepositoryAdapter",
    "PgTimeEntryRepositoryAdapter",
    # SQLite adapters (retained for standalone/local use)
    "SqliteDailyLogRepositoryAdapter",
    "SqliteSprintRepositoryAdapter",
    "SqliteSystemMetaRepositoryAdapter",
    "SqliteTaskRepositoryAdapter",
    "SqliteTimeEntryRepositoryAdapter",
]

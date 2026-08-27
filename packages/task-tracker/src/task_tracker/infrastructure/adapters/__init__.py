from task_tracker.infrastructure.adapters.daily_log import (
    SqliteDailyLogRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_daily_log import (
    PgDailyLogRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_system_meta import (
    PgSystemMetaRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.pg_task import PgTaskRepositoryAdapter
from task_tracker.infrastructure.adapters.system_meta import (
    SqliteSystemMetaRepositoryAdapter,
)
from task_tracker.infrastructure.adapters.task import (
    SqliteTaskRepositoryAdapter,
)

__all__ = [
    # Postgres adapters (the monorepo runtime — ADR-0008)
    "PgDailyLogRepositoryAdapter",
    "PgSystemMetaRepositoryAdapter",
    "PgTaskRepositoryAdapter",
    # SQLite adapters (retained for standalone/local use)
    "SqliteDailyLogRepositoryAdapter",
    "SqliteSystemMetaRepositoryAdapter",
    "SqliteTaskRepositoryAdapter",
]

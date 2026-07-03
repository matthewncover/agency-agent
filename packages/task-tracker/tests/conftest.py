import sqlite3

import pytest

from task_tracker.infrastructure.adapters import (
    SqliteDailyLogRepositoryAdapter,
    SqliteSprintRepositoryAdapter,
    SqliteSystemMetaRepositoryAdapter,
    SqliteTaskRepositoryAdapter,
    SqliteTimeEntryRepositoryAdapter,
)
from task_tracker.infrastructure.database import init_db


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def conn_factory(db_conn):
    return lambda: db_conn


@pytest.fixture
def task_repo(conn_factory):
    return SqliteTaskRepositoryAdapter(conn_factory)


@pytest.fixture
def time_entry_repo(conn_factory):
    return SqliteTimeEntryRepositoryAdapter(conn_factory)


@pytest.fixture
def sprint_repo(conn_factory):
    return SqliteSprintRepositoryAdapter(conn_factory)


@pytest.fixture
def daily_log_repo(conn_factory):
    return SqliteDailyLogRepositoryAdapter(conn_factory)


@pytest.fixture
def system_meta_repo(conn_factory):
    return SqliteSystemMetaRepositoryAdapter(conn_factory)

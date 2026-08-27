import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / "dev" / "task-tracker-mcp" / ".db" / "tasks.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS personal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    tier INTEGER,
    status TEXT NOT NULL DEFAULT 'not_started',
    blocked_reason TEXT,
    deadline DATE,
    parent_task_id INTEGER,
    is_commitment BOOLEAN NOT NULL DEFAULT 0,
    commitment_notes TEXT,
    priority_rank INTEGER,
    pinned BOOLEAN NOT NULL DEFAULT 0,
    private BOOLEAN NOT NULL DEFAULT 0,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at DATETIME,
    deleted_at DATETIME,
    FOREIGN KEY (parent_task_id) REFERENCES personal_tasks(id)
);

CREATE TABLE IF NOT EXISTS daily_logs (
    date DATE PRIMARY KEY,
    whoop_recovery INTEGER,
    whoop_hrv INTEGER,
    whoop_sleep_hours REAL,
    whoop_rhr INTEGER,
    reflection_moved_forward TEXT,
    reflection_didnt_move TEXT,
    reflection_do_differently TEXT,
    reflection_protect_tomorrow TEXT,
    observations TEXT,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS system_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TRIGGER IF NOT EXISTS personal_tasks_updated_at
    AFTER UPDATE ON personal_tasks
    FOR EACH ROW
BEGIN
    UPDATE personal_tasks
        SET updated_at = datetime('now', 'localtime')
        WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS daily_logs_updated_at
    AFTER UPDATE ON daily_logs
    FOR EACH ROW
BEGIN
    UPDATE daily_logs
        SET updated_at = datetime('now', 'localtime')
        WHERE date = NEW.date;
END;

CREATE TRIGGER IF NOT EXISTS system_meta_updated_at
    AFTER UPDATE ON system_meta
    FOR EACH ROW
BEGIN
    UPDATE system_meta
        SET updated_at = datetime('now', 'localtime')
        WHERE key = NEW.key;
END;
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


class ConnectionFactory:
    """Thread-safe connection factory. Creates a new connection per call.

    SQLite connections can't be shared across threads. MCP servers dispatch
    tool calls on arbitrary threads, so each operation needs its own connection.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)

    def __call__(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

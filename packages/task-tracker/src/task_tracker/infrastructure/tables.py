"""SQLAlchemy Core table definitions for the Postgres `tasktracker` schema.

Mirrors migrations 0003–0007 (personal-only since 0007, ADR-0019). Adapters
use these for typed, dialect-safe SQL — the monorepo convention is Core (not
the ORM) in infrastructure/.
"""

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    func,
)

metadata = MetaData(schema="tasktracker")

personal_tasks = Table(
    "personal_tasks",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "owner_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("title", Text, nullable=False),
    Column("tier", Integer),
    Column("status", Text, nullable=False, server_default="not_started"),
    Column("blocked_reason", Text),
    Column("deadline", Date),
    Column("parent_task_id", BigInteger, ForeignKey("tasktracker.personal_tasks.id")),
    Column("is_commitment", Boolean, nullable=False, server_default="false"),
    Column("commitment_notes", Text),
    Column("priority_rank", Integer),
    Column("pinned", Boolean, nullable=False, server_default="false"),
    Column("private", Boolean, nullable=False, server_default="false"),
    Column("notes", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Column("completed_at", TIMESTAMP(timezone=True)),
    Column("deleted_at", TIMESTAMP(timezone=True)),
)

daily_logs = Table(
    "daily_logs",
    metadata,
    Column(
        "owner_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("date", Date, primary_key=True),
    Column("whoop_recovery", Integer),
    Column("whoop_hrv", Integer),
    Column("whoop_sleep_hours", Float),
    Column("whoop_rhr", Integer),
    Column("reflection_moved_forward", Text),
    Column("reflection_didnt_move", Text),
    Column("reflection_do_differently", Text),
    Column("reflection_protect_tomorrow", Text),
    Column("observations", Text),
    Column("notes", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

system_meta = Table(
    "system_meta",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

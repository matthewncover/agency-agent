from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="goalbot")

chapter = Table(
    "chapter",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "owner_profile_id",
        BigInteger,
        ForeignKey("profile.profile.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("label", Text),
    Column("preamble", Text),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
)

goal = Table(
    "goal",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "owner_profile_id",
        BigInteger,
        ForeignKey("profile.profile.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "chapter_id",
        BigInteger,
        ForeignKey("goalbot.chapter.id", ondelete="SET NULL"),
    ),
    Column("title", Text, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column("archived_at", TIMESTAMP(timezone=True)),
)

goal_version = Table(
    "goal_version",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "goal_id",
        BigInteger,
        ForeignKey("goalbot.goal.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("version_no", Integer, nullable=False),
    Column("level", Text, nullable=False),
    Column("definition", Text, nullable=False),
    Column("why", Text),
    Column("recurrence_type", Text, nullable=False),
    Column("recurrence_config", JSONB, nullable=False),
    Column("completion_type", Text, nullable=False),
    Column("target_quantity", Numeric),
    Column("quantity_unit", Text),
    Column("task_ref_source", Text),
    Column("task_ref_id", Integer),
    Column(
        "effective_from",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column("effective_to", TIMESTAMP(timezone=True)),
    Column("lifecycle", Text, nullable=False, server_default="active"),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

anticipated_obstacle = Table(
    "anticipated_obstacle",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "goal_version_id",
        BigInteger,
        ForeignKey("goalbot.goal_version.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("text", Text, nullable=False),
)

rotation_group = Table(
    "rotation_group",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "owner_profile_id",
        BigInteger,
        ForeignKey("profile.profile.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    # ordered entries: {"goal_id": N} | {"rest": true}; refs validated at write
    Column("sequence", JSONB, nullable=False),
    Column("rotation_index", Integer, nullable=False, server_default="0"),
    Column("last_completed_at", TIMESTAMP(timezone=True)),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column("archived_at", TIMESTAMP(timezone=True)),
)

goal_state = Table(
    "goal_state",
    metadata,
    Column(
        "goal_id",
        BigInteger,
        ForeignKey("goalbot.goal.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("rotation_index", Integer),
    Column("last_completed_at", TIMESTAMP(timezone=True)),
    Column("carry_over_count", Integer, nullable=False, server_default="0"),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

daily_plan = Table(
    "daily_plan",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "person_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("plan_date", Date, nullable=False),
    Column("locked_in_at", TIMESTAMP(timezone=True)),
    Column("lock_was_explicit", Boolean, nullable=False, server_default="false"),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

daily_plan_item = Table(
    "daily_plan_item",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "daily_plan_id",
        BigInteger,
        ForeignKey("goalbot.daily_plan.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "goal_id",
        BigInteger,
        ForeignKey("goalbot.goal.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("goal_version_id", BigInteger, nullable=False),
    Column("status", Text, nullable=False, server_default="planned"),
    Column("quantity_actual", Numeric),
    Column("what_shifted", Text),
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

insight = Table(
    "insight",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "person_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("content", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="active"),
    Column("derived_from", JSONB),
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

win_log = Table(
    "win_log",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "person_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("goal_id", BigInteger, ForeignKey("goalbot.goal.id", ondelete="SET NULL")),
    Column("source", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

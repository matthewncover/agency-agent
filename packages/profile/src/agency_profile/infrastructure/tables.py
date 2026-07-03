from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
    MetaData,
    Table,
    Text,
    Time,
    func,
)

metadata = MetaData(schema="profile")

profile = Table(
    "profile",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("kind", Text, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

person = Table(
    "person",
    metadata,
    Column(
        "profile_id",
        BigInteger,
        ForeignKey("profile.profile.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("display_name", Text, nullable=False),
    Column("timezone", Text, nullable=False),
    Column("morning_prompt_local_time", Time, nullable=False),
)

group_profile = Table(
    "group_profile",
    metadata,
    Column(
        "profile_id",
        BigInteger,
        ForeignKey("profile.profile.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("label", Text, nullable=False),
)

group_member = Table(
    "group_member",
    metadata,
    Column(
        "group_profile_id",
        BigInteger,
        ForeignKey("profile.group_profile.profile_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "member_person_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

profile_doc = Table(
    "profile_doc",
    metadata,
    Column(
        "person_id",
        BigInteger,
        ForeignKey("profile.person.profile_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("content", Text, nullable=False),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

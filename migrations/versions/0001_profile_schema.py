"""profile schema (migration 0001)"""

from alembic import op

revision = "0001_profile_schema"
down_revision = None
branch_labels = None
depends_on = None

PROFILE_UP = r"""
CREATE SCHEMA IF NOT EXISTS profile;

CREATE TABLE profile.profile (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        text NOT NULL CHECK (kind IN ('person', 'group')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE profile.person (
    profile_id                 bigint PRIMARY KEY
                               REFERENCES profile.profile (id) ON DELETE CASCADE,
    display_name               text NOT NULL,
    timezone                   text NOT NULL,
    morning_prompt_local_time  time NOT NULL DEFAULT '06:00'
);

CREATE TABLE profile.group_profile (
    profile_id  bigint PRIMARY KEY
                REFERENCES profile.profile (id) ON DELETE CASCADE,
    label       text NOT NULL
);

CREATE TABLE profile.group_member (
    group_profile_id  bigint NOT NULL
                      REFERENCES profile.group_profile (profile_id) ON DELETE CASCADE,
    member_person_id  bigint NOT NULL
                      REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    PRIMARY KEY (group_profile_id, member_person_id)
);

CREATE TABLE profile.profile_doc (
    person_id   bigint PRIMARY KEY
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    content     text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
"""


def upgrade() -> None:
    op.execute(PROFILE_UP)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS profile CASCADE")

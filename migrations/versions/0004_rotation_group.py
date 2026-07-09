"""rotation groups (migration 0004, ADR-0016)"""

from alembic import op

revision = "0004_rotation_group"
down_revision = "0003_tasktracker_schema"
branch_labels = None
depends_on = None

ROTATION_GROUP_UP = r"""
CREATE TABLE goalbot.rotation_group (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    name              text NOT NULL,
    sequence          jsonb NOT NULL,
    rotation_index    int NOT NULL DEFAULT 0,
    last_completed_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz
);

CREATE INDEX rotation_group_owner_idx ON goalbot.rotation_group (owner_profile_id);
CREATE INDEX rotation_group_sequence_idx
    ON goalbot.rotation_group USING gin (sequence jsonb_path_ops);
"""


def upgrade() -> None:
    op.execute(ROTATION_GROUP_UP)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS goalbot.rotation_group")

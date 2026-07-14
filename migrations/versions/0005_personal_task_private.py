"""private flag on personal tasks (migration 0005, ADR-0018)"""

from alembic import op

revision = "0005_personal_task_private"
down_revision = "0004_rotation_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasktracker.personal_tasks "
        "ADD COLUMN private boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tasktracker.personal_tasks DROP COLUMN private")

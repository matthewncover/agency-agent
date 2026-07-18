"""chapter preamble — per-owner theme/focus/parked prose (migration 0006)"""

from alembic import op

revision = "0006_chapter_preamble"
down_revision = "0005_personal_task_private"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE goalbot.chapter ADD COLUMN preamble text")


def downgrade() -> None:
    op.execute("ALTER TABLE goalbot.chapter DROP COLUMN preamble")

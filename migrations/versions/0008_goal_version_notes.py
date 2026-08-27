"""goal_version.notes — authored logistics kept out of the bar text (0008)

Until now `notes:` lines in the goal markdown were folded into the bar
`definition` (never dropped, but they pollute what the bot reads as the bar).
Authored once per goal, written verbatim to all active versions, like `why`.
"""

from alembic import op

revision = "0008_goal_version_notes"
down_revision = "0007_personal_only_tasktracker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE goalbot.goal_version ADD COLUMN notes text")


def downgrade() -> None:
    op.execute("ALTER TABLE goalbot.goal_version DROP COLUMN notes")

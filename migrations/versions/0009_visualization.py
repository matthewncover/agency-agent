"""visualization capture — /visualize text reshared next morning (0009)

Free text the person sends before bed (a visualization exercise of what they
want tomorrow to look like). The next morning fire claims every unsurfaced row
and gives it back in their own words, with a light why link. `surfaced_on` is a
consume marker: once claimed, a row never resurfaces — no guilt trail.
"""

from alembic import op

revision = "0009_visualization"
down_revision = "0008_goal_version_notes"
branch_labels = None
depends_on = None

VISUALIZATION_UP = r"""
CREATE TABLE goalbot.visualization (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id   bigint NOT NULL
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    text        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    surfaced_on date
);

CREATE INDEX visualization_person_unsurfaced_idx
    ON goalbot.visualization (person_id) WHERE surfaced_on IS NULL;
"""


def upgrade() -> None:
    op.execute(VISUALIZATION_UP)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS goalbot.visualization")

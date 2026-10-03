"""routines schema: the morning checklist (0010)

Each person's current morning checklist: its items in order (one level of
sub-items, enforced in the app) and today's ticks. No day-by-day history:
`person_state.state_date` names the day the `checked` flags belong to, and a
stale day reads as all unchecked (lazy reset). `sent_date` is the day the
"Complete morning" message last went out, so it sends at most once a day.
"""

from alembic import op

revision = "0010_routines"
down_revision = "0009_visualization"
branch_labels = None
depends_on = None

ROUTINES_UP = r"""
CREATE SCHEMA IF NOT EXISTS routines;

CREATE TABLE routines.item (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id   bigint NOT NULL
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    parent_id   bigint REFERENCES routines.item (id) ON DELETE CASCADE,
    position    integer NOT NULL,
    text        text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 200),
    checked     boolean NOT NULL DEFAULT false
);

CREATE INDEX item_person_order_idx
    ON routines.item (person_id, parent_id, position);

CREATE TABLE routines.person_state (
    person_id   bigint PRIMARY KEY
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    state_date  date,
    sent_date   date
);
"""


def upgrade() -> None:
    op.execute(ROUTINES_UP)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS routines CASCADE")

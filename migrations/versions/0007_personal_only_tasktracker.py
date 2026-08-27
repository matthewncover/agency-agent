"""personal-only task-tracker (migration 0007, ADR-0019)

Drops the never-populated work half of the tasktracker schema (work tracking
moved to a separate work assistant; the legacy standalone SQLite keeps the
archival history) and narrows goal_version.task_ref_source to 'personal'.
Verified zero rows in all three tables (prod + dev) and zero 'work' refs
before authoring.
"""

from alembic import op

revision = "0007_personal_only_tasktracker"
down_revision = "0006_chapter_preamble"
branch_labels = None
depends_on = None

# time_entries FKs work_tasks; work_tasks FKs sprints — drop in that order.
UP = r"""
DROP TABLE tasktracker.time_entries;
DROP TABLE tasktracker.work_tasks;
DROP TABLE tasktracker.sprints;

ALTER TABLE goalbot.goal_version
    DROP CONSTRAINT goal_version_task_ref_source_check;
ALTER TABLE goalbot.goal_version
    ADD CONSTRAINT goal_version_task_ref_source_check
    CHECK (task_ref_source IN ('personal'));
"""

# Recreates the 0003 DDL verbatim (structure only — the dropped tables held
# zero rows, so downgrade restores schema, not data).
DOWN = r"""
ALTER TABLE goalbot.goal_version
    DROP CONSTRAINT goal_version_task_ref_source_check;
ALTER TABLE goalbot.goal_version
    ADD CONSTRAINT goal_version_task_ref_source_check
    CHECK (task_ref_source IN ('personal', 'work'));

CREATE TABLE tasktracker.sprints (
    id          text PRIMARY KEY,
    start_date  date NOT NULL,
    end_date    date NOT NULL,
    status      text NOT NULL DEFAULT 'active',
    notes       text
);

CREATE TABLE tasktracker.work_tasks (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id          bigint NOT NULL
                      REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    title             text NOT NULL,
    ods_ticket        text,
    sprint_id         text REFERENCES tasktracker.sprints (id),
    commitment_level  text,
    jn_bucket         text,
    status            text NOT NULL DEFAULT 'not_started',
    blocked_reason    text,
    estimate_hours    double precision,
    deadline          date,
    parent_task_id    bigint REFERENCES tasktracker.work_tasks (id),
    is_commitment     boolean NOT NULL DEFAULT false,
    commitment_notes  text,
    priority_rank     integer,
    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz,
    deleted_at        timestamptz
);

CREATE INDEX work_tasks_owner_idx  ON tasktracker.work_tasks (owner_id);
CREATE INDEX work_tasks_parent_idx ON tasktracker.work_tasks (parent_task_id);
CREATE INDEX work_tasks_sprint_idx ON tasktracker.work_tasks (sprint_id);

CREATE TABLE tasktracker.time_entries (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_task_id      bigint NOT NULL REFERENCES tasktracker.work_tasks (id),
    date              date NOT NULL,
    duration_minutes  integer NOT NULL,
    jn_bucket         text NOT NULL,
    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX time_entries_task_idx ON tasktracker.time_entries (work_task_id);
CREATE INDEX time_entries_date_idx ON tasktracker.time_entries (date);
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)

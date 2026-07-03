"""tasktracker schema (migration 0003)"""

from alembic import op

revision = "0003_tasktracker_schema"
down_revision = "0002_goalbot_schema"
branch_labels = None
depends_on = None

TASKTRACKER_UP = r"""
CREATE SCHEMA IF NOT EXISTS tasktracker;

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

CREATE TABLE tasktracker.personal_tasks (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id          bigint NOT NULL
                      REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    title             text NOT NULL,
    tier              integer,
    status            text NOT NULL DEFAULT 'not_started',
    blocked_reason    text,
    deadline          date,
    parent_task_id    bigint REFERENCES tasktracker.personal_tasks (id),
    is_commitment     boolean NOT NULL DEFAULT false,
    commitment_notes  text,
    priority_rank     integer,
    pinned            boolean NOT NULL DEFAULT false,
    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz,
    deleted_at        timestamptz
);

CREATE INDEX personal_tasks_owner_idx  ON tasktracker.personal_tasks (owner_id);
CREATE INDEX personal_tasks_parent_idx ON tasktracker.personal_tasks (parent_task_id);

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

CREATE TABLE tasktracker.daily_logs (
    owner_id                   bigint NOT NULL
                               REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    date                       date NOT NULL,
    whoop_recovery             integer,
    whoop_hrv                  integer,
    whoop_sleep_hours          double precision,
    whoop_rhr                  integer,
    reflection_moved_forward   text,
    reflection_didnt_move      text,
    reflection_do_differently  text,
    reflection_protect_tomorrow text,
    observations               text,
    notes                      text,
    created_at                 timestamptz NOT NULL DEFAULT now(),
    updated_at                 timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, date)
);

CREATE TABLE tasktracker.system_meta (
    key         text PRIMARY KEY,
    value       text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
"""


def upgrade() -> None:
    op.execute(TASKTRACKER_UP)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS tasktracker CASCADE")

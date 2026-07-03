"""goalbot schema (migration 0002)"""

from alembic import op

revision = "0002_goalbot_schema"
down_revision = "0001_profile_schema"
branch_labels = None
depends_on = None

GOALBOT_UP = r"""
CREATE SCHEMA IF NOT EXISTS goalbot;

CREATE TABLE goalbot.insight (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id     bigint NOT NULL
                  REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    content       text NOT NULL,
    status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','proposed_for_profile','graduated','dismissed')),
    derived_from  jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE goalbot.chapter (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    label             text,
    start_date        date NOT NULL,
    end_date          date NOT NULL,
    CHECK (end_date >= start_date)
);

CREATE TABLE goalbot.goal (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    chapter_id        bigint
                      REFERENCES goalbot.chapter (id) ON DELETE SET NULL,
    title             text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz
);

CREATE INDEX goal_owner_idx   ON goalbot.goal (owner_profile_id);
CREATE INDEX goal_chapter_idx ON goalbot.goal (chapter_id);

CREATE TABLE goalbot.tag (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

CREATE TABLE goalbot.goal_tag (
    goal_id  bigint NOT NULL REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    tag_id   bigint NOT NULL REFERENCES goalbot.tag  (id) ON DELETE CASCADE,
    PRIMARY KEY (goal_id, tag_id)
);

CREATE TABLE goalbot.goal_version (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    goal_id           bigint NOT NULL REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    version_no        int NOT NULL,
    level             text NOT NULL CHECK (level IN ('need','want')),
    definition        text NOT NULL,
    why               text,
    recurrence_type   text NOT NULL
                      CHECK (recurrence_type IN
                        ('oneoff','daily','rotation','quota',
                         'interval','fixed_schedule','accumulation')),
    recurrence_config jsonb NOT NULL,
    completion_type   text NOT NULL
                      CHECK (completion_type IN ('binary','quantity','duration')),
    target_quantity   numeric,
    quantity_unit     text,
    task_ref_source   text CHECK (task_ref_source IN ('personal','work')),
    task_ref_id       integer,
    effective_from    timestamptz NOT NULL DEFAULT now(),
    effective_to      timestamptz,
    lifecycle         text NOT NULL DEFAULT 'active'
                      CHECK (lifecycle IN ('active','paused','archived')),
    created_at        timestamptz NOT NULL DEFAULT now(),

    CHECK ((task_ref_source IS NULL) = (task_ref_id IS NULL)),

    UNIQUE (goal_id, id)
);

CREATE UNIQUE INDEX goal_version_current_uniq
    ON goalbot.goal_version (goal_id, level)
    WHERE effective_to IS NULL;

CREATE INDEX goal_version_goal_idx ON goalbot.goal_version (goal_id);

CREATE TABLE goalbot.goal_state (
    goal_id            bigint PRIMARY KEY REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    rotation_index     int,
    last_completed_at  timestamptz,
    carry_over_count   int NOT NULL DEFAULT 0,
    updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE goalbot.anticipated_obstacle (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    goal_version_id  bigint NOT NULL
                     REFERENCES goalbot.goal_version (id) ON DELETE CASCADE,
    text             text NOT NULL
);

CREATE TABLE goalbot.daily_plan (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id          bigint NOT NULL
                       REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    plan_date          date NOT NULL,
    locked_in_at       timestamptz,
    lock_was_explicit  boolean NOT NULL DEFAULT false,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (person_id, plan_date)
);

CREATE TABLE goalbot.daily_plan_item (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    daily_plan_id    bigint NOT NULL
                     REFERENCES goalbot.daily_plan (id) ON DELETE CASCADE,
    goal_id          bigint NOT NULL
                     REFERENCES goalbot.goal (id) ON DELETE RESTRICT,
    goal_version_id  bigint NOT NULL,
    status           text NOT NULL DEFAULT 'planned'
                     CHECK (status IN ('planned','done','partial','not_done','carried_over')),
    quantity_actual  numeric,
    what_shifted     text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    FOREIGN KEY (goal_id, goal_version_id)
        REFERENCES goalbot.goal_version (goal_id, id) ON DELETE RESTRICT
);

CREATE INDEX daily_plan_item_plan_idx ON goalbot.daily_plan_item (daily_plan_id);
CREATE INDEX daily_plan_item_goal_idx ON goalbot.daily_plan_item (goal_id);

CREATE TABLE goalbot.friction_log (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id           bigint NOT NULL
                        REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    goal_id             bigint REFERENCES goalbot.goal (id) ON DELETE SET NULL,
    daily_plan_item_id  bigint REFERENCES goalbot.daily_plan_item (id) ON DELETE SET NULL,
    text                text NOT NULL,
    logged_for_date     date NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX friction_log_person_idx ON goalbot.friction_log (person_id, logged_for_date);

CREATE TABLE goalbot.win_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id   bigint NOT NULL
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    goal_id     bigint REFERENCES goalbot.goal (id) ON DELETE SET NULL,
    source      text NOT NULL CHECK (source IN ('manual','derived')),
    text        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX win_log_person_idx ON goalbot.win_log (person_id);
"""


def upgrade() -> None:
    op.execute(GOALBOT_UP)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS goalbot CASCADE")

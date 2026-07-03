-- =====================================================================
-- Migration 0003 — task-tracker schema (package: `task-tracker`)
-- =====================================================================
-- Depends on migration 0002 (goalbot schema). Ports task-tracker's live
-- SQLite schema to a Postgres `tasktracker` schema on the shared instance
-- [ADR-0008]. Tables are carried over as-is (same columns, same domain)
-- with two deliberate changes:
--
--   1. Person-stamping [ADR-0004/0008]: `owner_id` is added to the owned
--      tables (work_tasks, personal_tasks) and FKs profile.person(profile_id),
--      so ownership is a DB guarantee. daily_logs' PK becomes (owner_id, date)
--      (architecture §7 OQ-D) — Whoop/sleep signal is per-person-per-day.
--   2. SQLite → Postgres type translation: AUTOINCREMENT → GENERATED ALWAYS
--      AS IDENTITY, DATETIME → timestamptz, REAL → double precision. The
--      SQLite updated_at triggers are dropped; updated_at is app-managed via
--      SQLAlchemy `onupdate` (monorepo convention).
--
-- sprints/system_meta stay global (single-user MVP, no owner_id). time_entries
-- derive ownership through their work_task. Cross-schema access to this schema
-- is only ever through task-tracker's typed read-only client [ADR-0007] — never
-- raw cross-schema SQL.
-- =====================================================================

-- migrate:up
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

-- migrate:down
DROP SCHEMA IF EXISTS tasktracker CASCADE;

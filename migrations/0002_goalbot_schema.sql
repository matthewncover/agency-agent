-- =====================================================================
-- Migration 0002 — goal-bot schema (package: `goal-bot`)
-- =====================================================================
-- Depends on migration 0001 (profile schema). Holds the goal domain plus
-- Tier-2 observations (friction_log + daily_plan_item.what_shifted) and
-- Tier-3 insights. All three memory tiers below stay domain-local to
-- goal-bot. [ADR-0011]
--
-- Cross-schema references to `profile` are real FKs (same database).
-- The ONLY application-enforced invariant is the task_ref owner-match,
-- because task-tracker lives in a separate schema and Postgres has no
-- cross-schema-with-business-rule FK. [ADR-0005/0007]
--
-- Person-only tables (daily_plan, friction_log, win_log, insight) FK to
-- profile.person(profile_id), which makes "person-only" a DB guarantee —
-- a strengthening over the spec's "application-enforced" note, available
-- because these point at the subtype PK, not the supertype.
-- =====================================================================
 
-- migrate:up
 
CREATE SCHEMA IF NOT EXISTS goalbot;
 
-- ---------------------------------------------------------------------
-- insight — TIER 3: AI-maintained, advisory, compressed
--   Auto-written by AI; graduates into profile.profile_doc ONLY on human
--   approval (status transition + an app-side write). [ADR-0011]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.insight (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id     bigint NOT NULL
                  REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    content       text NOT NULL,
    status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','proposed_for_profile','graduated','dismissed')),
    derived_from  jsonb,             -- pointers to the Tier-2 events behind it
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
 
-- ---------------------------------------------------------------------
-- chapter — the goal-setting block (was "cycle") [Decided §4]
--   owner_profile_id -> profile.profile: person OR group. [D-17]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.chapter (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    label             text,
    start_date        date NOT NULL,
    end_date          date NOT NULL,
    CHECK (end_date >= start_date)
);
 
-- ---------------------------------------------------------------------
-- goal — stable identity (identity = id, never content). [OQ-5]
--   chapter_id nullable: null = persists across windows untouched. [D-18]
--   archived_at nullable: lifecycle on the identity row (vs. `paused`,
--   which is a goal_version.lifecycle state — see set_goal_lifecycle in
--   mcp-tools.md §3.2).
--
--   OWNER<->CHAPTER MATCH (RESOLVED, ADR-0013): a goal's owner is
--   intentionally NOT constrained to equal its chapter's owner -- a personal
--   goal inside a shared (group) chapter is legitimate, so ownership equality
--   is deliberately not enforced here (no constraint, no trigger). The one
--   odd combination worth catching -- a group-owned goal inside an
--   individual's private chapter -- is a soft confirm-at-ingest check in
--   application logic, not a DB rule.
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.goal (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    chapter_id        bigint
                      REFERENCES goalbot.chapter (id) ON DELETE SET NULL,
    title             text NOT NULL,      -- human label; NOT used to infer identity
    created_at        timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz
);
 
CREATE INDEX goal_owner_idx   ON goalbot.goal (owner_profile_id);
CREATE INDEX goal_chapter_idx ON goalbot.goal (chapter_id);
 
-- ---------------------------------------------------------------------
-- tag / goal_tag — grouping, orthogonal to identity [Decided §4]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.tag (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL UNIQUE       -- e.g. 'movement','health','relationship'
);
 
CREATE TABLE goalbot.goal_tag (
    goal_id  bigint NOT NULL REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    tag_id   bigint NOT NULL REFERENCES goalbot.tag  (id) ON DELETE CASCADE,
    PRIMARY KEY (goal_id, tag_id)
);
 
-- ---------------------------------------------------------------------
-- goal_version — mutable content, versioned + effective-dated. [OQ-5/14]
--   need/want lives HERE via `level`. A goal with both a need-form and a
--   want-form has TWO concurrently-effective versions (one per level);
--   both are valid. So versioning is per (goal_id, level): raising the
--   need bar opens a new need version and leaves the want untouched.
--
--   version_no: monotonic per (goal_id, level) by convention (display/
--   ordering aid; not load-bearing — effective_from is the source of truth).
--
--   task_ref_*: one-off goals only [ADR-0005]. task_ref_id is a reference
--   INTO task-tracker, NOT a DB FK (separate schema). The invariant that
--   the referenced task's owner matches the goal's owner is APPLICATION-
--   ENFORCED at write via the typed task client. [ADR-0005/0007]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.goal_version (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    goal_id           bigint NOT NULL REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    version_no        int NOT NULL,
    level             text NOT NULL CHECK (level IN ('need','want')),
    definition        text NOT NULL,     -- the bar text
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
    task_ref_id       integer,           -- reference into task-tracker; NOT a FK.
                                         --   integer to match task-tracker's PK
                                         --   (separate schema, integer autoincrement).
    effective_from    timestamptz NOT NULL DEFAULT now(),
    effective_to      timestamptz,       -- null = current
    lifecycle         text NOT NULL DEFAULT 'active'
                      CHECK (lifecycle IN ('active','paused','archived')),
    created_at        timestamptz NOT NULL DEFAULT now(),
 
    -- task_ref is all-or-nothing
    CHECK ((task_ref_source IS NULL) = (task_ref_id IS NULL)),
 
    -- enables the composite FK from daily_plan_item that guarantees a
    -- pinned version actually belongs to the stated goal (see below).
    UNIQUE (goal_id, id)
);
 
-- At most ONE current (open-ended) version per (goal, level). This is the
-- real versioning invariant — a goal can't have two live need bars.
CREATE UNIQUE INDEX goal_version_current_uniq
    ON goalbot.goal_version (goal_id, level)
    WHERE effective_to IS NULL;
 
CREATE INDEX goal_version_goal_idx ON goalbot.goal_version (goal_id);
 
-- ---------------------------------------------------------------------
-- goal_state — per-goal mutable state (one row per goal). [§5]
--   rotation_index / last_completed_at are null for goals that don't use
--   them. carry_over_count lives HERE (not on daily_plan_item) so it
--   survives across days; per ENGAGEMENT-NOT-FAILURE it is advanced only
--   on engaged-but-unmoved days by goal-bot logic — it is NOT a raw tally
--   of carried_over items, and silence never advances it. [mcp-tools §4.1]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.goal_state (
    goal_id            bigint PRIMARY KEY REFERENCES goalbot.goal (id) ON DELETE CASCADE,
    rotation_index     int,                              -- rotation pointer (completion-advanced)
    last_completed_at  timestamptz,                      -- also supports `interval`
    carry_over_count   int NOT NULL DEFAULT 0,           -- drives the ~1-week reassessment nudge
    updated_at         timestamptz NOT NULL DEFAULT now()
);
 
-- ---------------------------------------------------------------------
-- anticipated_obstacle — obstacles listed at authoring time
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.anticipated_obstacle (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    goal_version_id  bigint NOT NULL
                     REFERENCES goalbot.goal_version (id) ON DELETE CASCADE,
    text             text NOT NULL
);
 
-- ---------------------------------------------------------------------
-- daily_plan — one per PERSON per day. Groups don't get plans; group
--   goals fan out into each member's plan. [§5/§8]
--   person_id -> profile.person enforces person-only at the DB level.
--   The "day" runs to the next 6a local boundary — that's a read/write
--   semantic in app logic, NOT a column. [Decided §8]
-- ---------------------------------------------------------------------
CREATE TABLE goalbot.daily_plan (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id          bigint NOT NULL
                       REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    plan_date          date NOT NULL,
    locked_in_at       timestamptz,        -- null = never explicitly locked (implied lock)
    lock_was_explicit  boolean NOT NULL DEFAULT false,   -- pattern-mining data, NOT a gate
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (person_id, plan_date)
);
 
-- ---------------------------------------------------------------------
-- daily_plan_item — a goal placed on a day, pinned to the version
--   committed that day. [OQ-14 pin]
--   The composite FK (goal_id, goal_version_id) -> goal_version(goal_id, id)
--   guarantees the pinned version belongs to the stated goal. ON DELETE
--   RESTRICT on that FK protects history: a version can't be deleted out
--   from under a day that committed to it.
--   The version's `level` already says need/want, so no separate
--   classification column. [Decided §3]
-- ---------------------------------------------------------------------
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
    what_shifted     text,              -- TIER 2: the morning-after reflection
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
 
    -- pin integrity: version must belong to this goal; can't be hard-deleted
    FOREIGN KEY (goal_id, goal_version_id)
        REFERENCES goalbot.goal_version (goal_id, id) ON DELETE RESTRICT
);
 
CREATE INDEX daily_plan_item_plan_idx ON goalbot.daily_plan_item (daily_plan_id);
CREATE INDEX daily_plan_item_goal_idx ON goalbot.daily_plan_item (goal_id);
 
-- ---------------------------------------------------------------------
-- friction_log — TIER 2: OBSERVED obstacles; the pattern-mining gold.
--   Append-only events (nothing reads the whole log live). [§7b]
-- ---------------------------------------------------------------------
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
 
-- ---------------------------------------------------------------------
-- win_log — [OQ-13] manual entries any time + AI-derived from done items.
-- ---------------------------------------------------------------------
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
 
-- migrate:down
 
DROP SCHEMA IF EXISTS goalbot CASCADE;
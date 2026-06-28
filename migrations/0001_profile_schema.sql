-- =====================================================================
-- Migration 0001 — profile schema (package: `profile`)
-- =====================================================================
-- Identity is a shared agency-agent primitive. `profile` is the supertype
-- (one id space) so a single owner_profile_id FK elsewhere can point at
-- either an individual or a group with no 'shared'/null special-case.
--   [D-17 / ADR-0012]
--
-- Deploys standalone (profile + task-tracker, no goal-bot) per meta-plan §3.
--
-- Conventions (whole project):
--   * PKs: bigint generated always as identity. [decided]
--   * Enums: text + CHECK, not native enum types — values are expected to
--     grow and native enums are awkward to alter (spec §6a: enum values are
--     cheap-to-change). [decided]
--   * updated_at: application-managed (SQLAlchemy onupdate=now()), no DB
--     triggers. Covers every write through the ORM/FastMCP path; the only
--     gap is hand-written SQL, accepted at this scale. [decided]
-- =====================================================================
 
-- migrate:up
 
CREATE SCHEMA IF NOT EXISTS profile;
 
-- ---------------------------------------------------------------------
-- profile — IDENTITY SUPERTYPE (shared id space)
-- ---------------------------------------------------------------------
CREATE TABLE profile.profile (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        text NOT NULL CHECK (kind IN ('person', 'group')),
    created_at  timestamptz NOT NULL DEFAULT now()
);
 
-- ---------------------------------------------------------------------
-- person — subtype of profile (shared-PK pattern)
--   profile_id IS the identity, not a separate id.
-- ---------------------------------------------------------------------
CREATE TABLE profile.person (
    profile_id                 bigint PRIMARY KEY
                               REFERENCES profile.profile (id) ON DELETE CASCADE,
    display_name               text NOT NULL,
    timezone                   text NOT NULL,            -- IANA tz, e.g. 'America/Los_Angeles'
    morning_prompt_local_time  time NOT NULL DEFAULT '06:00'
    -- channel-agnostic: the telegram_user_id -> person map is a RUNTIME concern
    --   (agent module), NOT a profile column. [ADR-0004, unchanged by ADR-0014]
);
 
-- ---------------------------------------------------------------------
-- group_profile — subtype of profile: a couple / household
-- ---------------------------------------------------------------------
CREATE TABLE profile.group_profile (
    profile_id  bigint PRIMARY KEY
                REFERENCES profile.profile (id) ON DELETE CASCADE,
    label       text NOT NULL            -- e.g. 'Matthew & Jade'
);
 
-- ---------------------------------------------------------------------
-- group_member — which persons belong to a group
--   Members are persons only; no nested groups for MVP. The FK to
--   profile.person (not profile.profile) enforces "members are persons"
--   at the DB level.
-- ---------------------------------------------------------------------
CREATE TABLE profile.group_member (
    group_profile_id  bigint NOT NULL
                      REFERENCES profile.group_profile (profile_id) ON DELETE CASCADE,
    member_person_id  bigint NOT NULL
                      REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    PRIMARY KEY (group_profile_id, member_person_id)
);
 
-- ---------------------------------------------------------------------
-- profile_doc — TIER 1: authored, human-owned, trusted (per-person)
--   Only humans (or human-approved AI proposals) write here. [ADR-0011]
--   Single-blob model: ONE row per person; the doc is sectioned by
--   convention inside `content` (markdown headers: identity, priorities,
--   schedule, personality, patterns — spec §7b), not by rows. person_id
--   is the PK, which makes one-doc-per-person a DB guarantee. person_id
--   FK -> profile.person enforces person-only (groups get no profile).
--   updated_at is application-managed (SQLAlchemy onupdate); no trigger.
-- ---------------------------------------------------------------------
CREATE TABLE profile.profile_doc (
    person_id   bigint PRIMARY KEY
                REFERENCES profile.person (profile_id) ON DELETE CASCADE,
    content     text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
 
-- migrate:down
 
DROP SCHEMA IF EXISTS profile CASCADE;
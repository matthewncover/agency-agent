-- ============ goalbot schema — rotation groups (ADR-0016) ============
-- A rotation group is a cross-goal cadence SCHEDULER, not a goal: it has no
-- versions, no need/want, no wins, and is never itself completable. Member
-- goals stay first-class (own bars, own logging, own lineage); the group owns
-- only the shared pointer that decides whose day it is.
--
--   sequence: ordered jsonb entries, each {"goal_id": N} or {"rest": true}.
--     Goal refs are APPLICATION-VALIDATED at write (same precedent as the
--     person-only FK rule, spec §6) — jsonb can't carry a real FK. A goal may
--     belong to at most one active group (app-enforced): the group is its
--     sole scheduler, and two schedulers would be ambiguous.
--   rotation_index / last_completed_at: the shared pointer. Advances only on
--     an engaged `done` (from the SURFACED entry); a miss holds it; silence
--     touches nothing (NULL-TOLERANCE).
--   Chapters: member goals are chapter-scoped (ADR-0013) and rollover mints
--     fresh goal ids, so groups referencing closed goals are stale by
--     construction — ingest re-resolves membership by gid at rollover.

CREATE TABLE goalbot.rotation_group (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_profile_id  bigint NOT NULL
                      REFERENCES profile.profile (id) ON DELETE RESTRICT,
    name              text NOT NULL,
    sequence          jsonb NOT NULL,
    rotation_index    int NOT NULL DEFAULT 0,
    last_completed_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz
);

CREATE INDEX rotation_group_owner_idx ON goalbot.rotation_group (owner_profile_id);
-- membership lookups ("which active group schedules goal N?") use containment
CREATE INDEX rotation_group_sequence_idx
    ON goalbot.rotation_group USING gin (sequence jsonb_path_ops);

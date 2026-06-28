# ADR-0012: Group/household profile owns shared goals via a `profile` supertype
 
**Status:** Accepted
 
**Supersedes:** ADR-0004 (re-stating its still-valid parts below).
 
## Context
ADR-0004 placed identity in a `profile` package and made `person_id` caller-supplied, but modeled shared goals/chapters with an `owner_scope ∈ {individual,shared}` enum plus a nullable `person_id` (null = shared). Chat-T (D-17) surfaced two problems with that flag:
1. **It's a special-case that leaks.** Every read of an owning row must branch on `owner_scope` and handle the null `person_id`. That branch reappears in surfacing, completion, and shared-state logic.
2. **It can't represent more than one sharing group.** `owner_scope='shared'` names *the* shared bucket. Family/household expansion (you + a future child; or two distinct sharing groups) has no representation — it would be a rewrite, not a migration, exactly the load-bearing kind the spec's §6a warns against deciding late.
A group is an *identity*, like a person. The clean model gives person and group a shared id space so a single owner FK can point at either.
 
## Decision
**Re-stated from ADR-0004 (still in force):**
- Identity + the **Tier-1 authored profile** live in the **`profile`** package/schema (human-owned ground truth).
- **`person_id` is caller-supplied** on every task/goal client + MCP call from day one; no global "current person."
- `profile.person` is **channel-agnostic**; the `telegram_user_id → person` map is a runtime concern (the agent module, now internal per ADR-0014), not a profile column.
- **Standalone task-tracker = `profile` + `task-tracker`.**
**New (the group-profile model):**
- `profile` is an **identity supertype**: `profile(id, kind ∈ {person, group})`, one shared id space.
- `person` and `group_profile` are **subtypes** (shared-PK pattern): `person.profile_id` / `group_profile.profile_id` each PK-and-FK to `profile.id`. `person` carries display_name/timezone/morning-time; `group_profile` carries a label.
- A **`group_member`** relation maps a group to its member persons (`(group_profile_id, member_person_id)`). Members are persons only; **no nested groups** for MVP.
- Every owning row uses a single **`owner_profile_id → profile.id`** — on **`goal` and `chapter`**. The `owner_scope` enum and the nullable `person_id`/null-means-shared convention are **removed** from both tables.
- A "shared" goal is just a goal whose `owner_profile_id` resolves to a group profile. It inherits all recurrence/completion semantics with no special rule.
## Consequences
- **The `owner_scope`/null special-case is deleted** on `goal` and `chapter`; one FK, one referent, no read-time branch.
- **OQ-16 is dissolved.** A group goal follows the normal recurrence semantics of its `recurrence_type` (daily resets daily, accumulation persists to the chapter target, one-off persists until done) — there is no separate shared-goal reset-vs-persist question. Spec §8/§10 mark it resolved.
- **Fan-out surfacing is the cost.** Groups don't get a `daily_plan`; a group goal fans out into each member's morning as the "separate response block" (OQ-9), and either member completing it writes shared completion state. This is surfacing logic, not new schema.
- **ADR-0007's "Person port" widens to a "Profile port"** that can resolve a profile to its kind and, for groups, enumerate members. task-tracker's `owner_id` continues to reference person-profiles (it has no group concept); only goal-bot/chapters use group owners. 0007 is not superseded — this is a noted widening.
- **Scales to family/household expansion** without a migration: a new group is a new `profile` row + memberships.
- Architecture §9's `owner_id → profile.person` instruction is superseded by this `owner_profile_id → profile.id` supertype column (the later, more general decision wins).

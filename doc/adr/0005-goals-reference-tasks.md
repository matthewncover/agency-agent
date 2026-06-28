# ADR-0005: One-off goals reference tasks (goal → task); concepts stay distinct
 
**Status:** Accepted
 
## Context
A one-off goal resembles a `personal_tasks` row but carries different semantics (`why`/`obstacles`/`level`/`chapter`/version lineage vs. `tier`/`priority_rank`/`is_commitment`/`pinned`). Chapter-setting will propose candidates from past goals + open tasks. The standalone constraint and the rejected merged-base-table (`actionable_item`) still hold. task-tracker has two independent id spaces (`work_tasks`, `personal_tasks`) and is now person-aware (ADR-0004).
 
## Decision
- Goal and task stay **distinct concepts** linked by an **optional reference on the goal**.
- `goal_version` (one-off only) MAY carry `task_ref = (source, id)`, `source ∈ {personal, work}` — source tag mandatory (independent id spaces).
- Recurring goals never carry `task_ref`.
- **Direction goal → task**, forced by standalone (task-tracker can't import goal-bot).
- **Invariant:** a goal owned by person P may only reference a task owned by P (enforceable now that both sides carry `profile.person`).
- **Promotion** = create a goal pointing at the existing task; task not moved/copied.
- Candidate-gathering = `personal_tasks WHERE tier IN (2,3) AND owner_id = P`; `work_tasks` excluded (no work goals).
- **MVP completion one-way:** goal is source of truth for the goal's status; goal-bot reads task status, no write-back.
## Consequences
- No concept duplication; no merged model; standalone task views unaffected.
- Tier-3 `pinned` items map onto self-actualization goal candidates.
- Two-way completion sync deferred to a future ADR.
- Spec edits: `task_ref_source`/`task_ref_id` on `goal_version`; tier-2/3 owner-scoped candidate note in §4.

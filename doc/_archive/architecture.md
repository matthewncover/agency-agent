> SUPERSEDED — retired by ADR-0012 (ownership) and ADR-0014 (packages). Historical only; do not use as a source of truth.

# agency-agent — Architecture & Integration Boundary
 
> **Doc:** `doc/architecture/architecture.md` · **v0.3** · status: draft, structural decisions settled; cross-bot synthesis parked as future
> **Role:** Resolve identity, task↔goal, package/MCP shape, and the agent/domain/composition split for the `agency-agent` monorepo against the live task-tracker schema.
> **v0.2 → v0.3:** five-package decomposition (`agent`, `profile`, `task-tracker`, `goal-bot`, `app`). Agent extracted from goal-bot as a domain-agnostic runtime depending on capability ports. Data package named `profile` (not `shared`). Composition root (`app`) separated from agent core. `person_id` is a caller-supplied parameter from day one (multi-user in ~2 months). Work tables ported as-is (not deprecated now). Periodic profile-synthesis recorded as a future idea, not built.
 
---
 
## 0. Naming
 
- **agency-agent** — the system / monorepo / the shared agent infrastructure.
- **agent** — the domain-agnostic runtime (scheduler, Telegram, LLM loop) that takes on a persona/capability. Could run standalone.
- **goal-bot** — the goals-oriented capability (goal domain + goal MCP + goal-specific memory) delivered through the agent over Telegram.
- **profile** — the shared per-person substrate (identity + authored profile).
- **task-tracker** — keeps its name.
---
 
## 1. Database engine — RESOLVED
 
**Migrate task-tracker SQLite → Postgres** as a clean-architecture adapter swap (write Postgres repository adapters; domain/use-case layers untouched). ~100 rows; CSV dump/load acceptable. Confirms ADR-0003 (not superseded) and unblocks the shared `profile` schema. **Work tables (`work_tasks`, `time_entries`, `sprints`) port as-is** — work is not being deprecated now; Matthew wants the history and a likely future work-specific surface. (ADR-0008, ADR-0009.)
 
---
 
## 2. Identity & the `profile` package
 
**Decision:** identity is a shared agency-agent primitive owned by a **`profile`** package/schema (named for what it owns, not a `shared` junk-drawer). `profile` owns `person` and the **Tier-1 authored profile** ("who this person is", human-owned).
 
- `profile.person` is **channel-agnostic**; the `telegram_user_id → person_id` map lives in the **agent** layer.
- task-tracker and goal-bot both link their rows to `profile.person` via `owner_id`.
- **`person_id` is a caller-supplied parameter on every task/goal client + MCP call from day one.** No global "current person." Single-user MVP just passes the one id; multi-user (≈2 months out) needs no retrofit. Row-level always-filter-by-owner enforcement lands with the second user.
- **Standalone task-tracker = `profile` + `task-tracker`** (no goal-bot). `profile` is a thin substrate, so "tasks without goals" holds.
→ ADR-0004 (revised: `profile` naming + caller-supplied `person_id`).
 
---
 
## 3. Memory & observation boundaries
 
Observations stay with the domain that produces and consumes them; only human-validated cross-domain knowledge reaches `profile`.
 
- **Task observations** (task context, planning signals for the task capability) live in **task-tracker** (its existing `daily_logs.observations`, Whoop, EOD reflection fields — ported as-is).
- **Goal observations + goal insights** (Tier-2 `what_shifted`/friction events, Tier-3 goal pattern digest) live in **goal-bot**.
- **Tier-1 authored profile** lives in **`profile`** — the only memory both capabilities treat as ground truth.
- **Cross-bot synthesis layer (FUTURE, not MVP):** the agent can mine *both* observation streams to form hypotheses about the individual and *propose* them for the shared profile. Periodic (≈10-week) cadence: surface "here's what I've noticed — which are true / how much do they matter / weight or exclude from context?", human validates, approved items graduate into Tier-1. **Build as an on-demand MCP tool the human calls (compare profile vs. logs), not an automatic background writer.** Parked in `doc/future-ideas.md`; do not build for MVP.
→ Trust boundary preserved: nothing the agent infers silently rewrites the authored profile.
 
---
 
## 4. Task ↔ one-off goal relationship
 
Unchanged in substance; person-aware.
 
- `goal_version` (one-off only) MAY carry `task_ref = (source, id)`, `source ∈ {personal, work}` — source tag mandatory (independent id spaces; both tables present since work is retained).
- Recurring goals never carry `task_ref`.
- Direction **goal → task**, forced by standalone (task-tracker can't import goal-bot).
- Invariant: a goal owned by P may only reference a task owned by P (checkable via `profile.person` on both sides).
- Promotion = create a goal pointing at the existing task; task not moved/copied.
- Candidate-gathering = `personal_tasks WHERE tier IN (2,3) AND owner_id = P`; `work_tasks` excluded from goal candidates (no work goals), though the table is retained.
- MVP completion one-way: goal is source of truth for the goal's status; goal-bot reads task status, no write-back.
→ ADR-0005.
 
---
 
## 5. Packages, the agent/domain/composition split, MCP surface
 
**Decision (MVP): five packages.**
 
```
packages/
  profile/        person + Tier-1 authored profile (+ future cross-bot insights).   deps: none
  task-tracker/   tasks (personal + work) + task observations + own MCP.            deps: profile
  goal-bot/       goal domain + goal MCP + Tier-2/3 goal memory.                     deps: profile, task-tracker
  agent/          domain-agnostic runtime: scheduler + Telegram + LLM loop;          deps: profile + capability PORTS only
                  orchestration is abstract — knows ports, not concrete capabilities.
  app/            composition root: the one place allowed to know concretes —        deps: agent, goal-bot, task-tracker, profile
                  instantiates adapters (Telegram, goal capability, task client) and wires them into agent's ports. The process entrypoint.
```
 
- **`agent` does not import `goal-bot` or `task-tracker`.** It depends on capability ports + `profile`. This is what makes "agent could run standalone" real, not aspirational.
- **`app` is the composition root** — clean architecture's sanctioned rule-breaker: the only place that names concrete adapters and plugs them in. Everything else sees ports.
- **Keep the capability port minimal for MVP** (one capability: goals). Generalize only when task-tracker actually plugs in as a second capability. No plugin framework.
- This reverses v0.2's "bot folded into goal-bot": the agent's second consumer (multi-user task-tracker) is ~2 months out, so the seam is near-term, not hypothetical — cheaper to build now than retrofit.
**MCP surface:**
- task-tracker MCP (existing) — task CRUD, `person_id` param; standalone + task chats.
- goal MCP (new, goal-bot) — goal/chapter/daily-plan/reflection, `person_id` param.
- The morning-ritual LLM (driven by `agent`) gets the **goal MCP only**; candidate-gathering is done by goal-bot via the typed task client and surfaced as a prepared list. The LLM never holds task-tracker's MCP.
→ ADR-0006 (revised: five packages), ADR-0010 (NEW: agent/domain/composition split).
 
---
 
## 6. Cross-package access — published ports, no raw cross-schema SQL
 
Both packages on Postgres, so cross-schema SQL is physically possible and still disallowed (clean-arch boundary, ADR-0009).
 
1. **`profile.person` + Tier-1:** through `profile`'s published repository port. Both capabilities depend on `profile`'s public API, not its tables.
2. **Task data (goal-bot → task-tracker):** task-tracker's **typed, read-only client** (published port) — candidate-gathering, referenced-task status, `daily_logs` Whoop/sleep reads. Not MCP transport (unreliable for deterministic sync); not raw cross-schema SQL.
3. **agent → capabilities:** through capability ports wired at `app`. The agent issues abstract operations; `app` binds them to goal-bot (and later task-tracker).
4. Read-only for MVP. The one anticipated cross-package *write* is future Tier-3→Tier-1 graduation, through `profile`'s port, gated by human approval (see §3).
→ ADR-0007.
 
---
 
## 7. Dependency graph (standalone preserved)
 
```
                    ┌─────────────────────────────┐
                    │ app  (composition root)     │
                    │  wires concretes → ports    │
                    └───┬─────────┬─────────┬──────┘
            ┌───────────┘         │         └───────────┐
            ▼                     ▼                     ▼
      ┌──────────┐        ┌──────────────┐       ┌──────────────┐
      │ agent    │  ....> │ goal-bot     │ ────> │ task-tracker │
      │ (ports)  │ ports  │ goal MCP     │ typed │ task MCP     │
      └────┬─────┘        └──────┬───────┘ client└──────┬───────┘
           │ Person port         │ Person port          │ Person port
           └─────────────┬───────┴──────────────────────┘
                         ▼
                   ┌──────────────────────────┐
                   │ profile: person + Tier-1 │  deps: none
                   └──────────────────────────┘
 
Standalone deploy = profile + task-tracker (no goal-bot, no agent, no goal concept).
Acyclic. agent → {profile, ports}.  goal-bot → {profile, task-tracker}.  task-tracker → profile.  profile → ∅.
task-tracker never imports goal-bot or agent.
```
 
---
 
## 8. Settled answers (this round)
 
- **OQ-A** → `packages/agent` (standalone-capable runtime) **+** `packages/profile` (person + Tier-1). Data package named `profile`, not `shared`.
- **OQ-B** → `profile` holds `person` only for MVP; cross-bot insight scaffolding noted as future.
- **OQ-C** → Tier-1 authored profile → `profile`; Tier-2/3 stay domain-local (task obs in task-tracker, goal obs in goal-bot); cross-domain synthesis is a future on-demand MCP tool with a human gate.
- **OQ-D** → owner-stamp `personal_tasks`/`work_tasks`/`daily_logs` (`daily_logs` PK → `(owner_id, date)`); `time_entries` inherits; `sprints`/`system_meta` global for MVP. Work retained, not deprecated.
- **OQ-E** → person-stamped + `person_id` param everywhere now; single active user for MVP; multi-user ≈2 months, no schema retrofit needed.
## 9. Flagged: revisions to spec & meta-plan (follow-up edit pass)
 
**`goal-bot-spec.md`:**
- §6: `person` + Tier-1 authored profile move to the **`profile`** schema; add `owner_id → profile.person` on goal tables; add `task_ref_source`/`task_ref_id` (nullable, one-off only) to `goal_version`. Tier-2/3 goal memory stays in goal-bot.
- §3: the morning ritual splits — the generic loop (schedule → build context → LLM turn → deliver → persist) belongs to **agent**; goal-specific logic (smart-subset, need/want, carry-over, lighter-day nudge) stays in goal-bot behind the capability port. (See FU-5.)
- §4: candidates = `personal_tasks` tier 2–3, owner-scoped.
**`meta-plan.md`:**
- §2 L36: "separate schemas on one Postgres instance" confirmed (task-tracker migrates); ADR-0003 stands.
- §3 L25–27/L78: replace the layout with the five packages (`agent`, `profile`, `task-tracker`, `goal-bot`, `app`); `shared` is renamed `profile`; no separate `bot` (it's the `agent` runtime).
- Apply the §0 naming convention throughout.
**New docs:**
- `doc/future-ideas.md`: periodic (~10-week) profile-synthesis tool — agent proposes insights from both observation streams, human validates/weights/excludes, approved items graduate into Tier-1; on-demand MCP tool, not automatic.
## 10. Build-order note (Matthew's framing, recorded — not a commitment)
 
Expect heavy downscoping at build time. Likely first slices: (1) stand up the `agent` runtime alone — verify Telegram wiring + context reading; (2) add the goal capability + goal MCP as one thing; (3) refactor/migrate task-tracker + its MCP; (4) test the two capabilities together. This doc defines target boundaries, not the implementation sequence.
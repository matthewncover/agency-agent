# agency-agent — Project Meta-Plan v0.3
 
> The organizing spine for **agency-agent** (the monorepo — "an agent to develop agency"), which houses the **goal-bot** and **task-tracker** packages. Defines how we split the work across **docs** and **chats**, the **repo** layout, the **conventions** (ADRs + index, glossary, CLAUDE.md, `.claude/rules/`), and the **sequence**. Lives at the repo root once the repo exists.
>
> **v0.2 → v0.3 (structural pass):** package layout updated to match doc/_archive/architecture.md v0.3 and ADR-0014 — `shared` is renamed **`profile`**; the runtime is the **`agent`** concern (no separate `bot`); but the standalone **`agent`/`app` package split is deferred for MVP (ADR-0014), landing the MVP at **three packages** (`profile`, `task-tracker`, `goal-bot`) with the agent-runtime/composition boundary kept as an *in-code module line*, extractable later. §2/§3 reflect this.
 
---
 
## 1. Operating principle — why split at all
 
We're deliberately fragmenting the work into single-responsibility **docs** and focused **chats**. The reason is mechanical, not cosmetic:
 
- **Per-chat context budget.** A fresh chat that owns one concern (e.g. "the markdown ingestion template") and has only the relevant doc attached reasons far better than one chat carrying the whole project. We trade breadth for depth on purpose.
- **One canonical home per concern.** Each fact lives in exactly one doc. No duplication → no drift. Other docs *link*, they don't *restate*.
- **Settled things stay settled.** The **glossary** pins vocabulary and the **ADRs** pin decisions *with their rationale*, so a later chat (or Claude Code) doesn't relitigate a call we already reasoned through.
The master `goal-bot-spec.md` (currently v0.4) was the right tool for *thinking*; it's now too broad to be a working doc. Phase 1 decomposes it into the taxonomy below, after which it retires (or becomes just the product/behavior spec).
 
---
 
## 2. Repo strategy — **recommendation: monorepo with package boundaries**
 
You floated separate repos (task-tracker independent of goal-bot, so someone could use tasks without goals). That goal is real, but a **repo** boundary is the wrong tool for it *right now*; a **package** boundary serves it better.
 
**Recommendation:** one repo named **`agency-agent`**, internal packages (MVP = three; ADR-0014):
```
/packages/profile        ← identity (profile/person/group) + Tier-1 authored profile; deps: none
/packages/task-tracker   ← deployable on its own; preserves "tasks without goals"; deps: profile
/packages/goal-bot       ← goal domain + goal MCP + Tier-2/3 goal memory; deps: profile, task-tracker
                            also hosts the agent-runtime loop (scheduler/Telegram/LLM) and the
                            composition entrypoint as INTERNAL MODULES for MVP — kept behind a
                            clean module boundary so the standalone `agent`/`app` packages can be
                            lifted out later without a rewrite (ADR-0014, supersedes ADR-0010's
                            packaging; revises ADR-0006 from five packages to three).
```
 
> **Why not the five-package split now (agent + app).** ADR-0006/0010 specced a domain-agnostic `agent` runtime and an `app` composition root as separate packages, justified by a second capability (multi-user task-tracker) ~2 months out. That bet was taken off the table for MVP (ADR-0014): clean architecture (ADR-0009) already makes extracting a clean runtime later a lift-out, so the package seam earns nothing now and costs idle abstraction if the horizon slips. The *discipline* that replaces the seam is a strict in-code module line — agent-generic logic and goal-specific logic do not bleed together. Revisit if/when the second capability actually lands.
 
**Why monorepo now:**
- The two systems are **co-evolving precisely now** (we're designing the integration boundary this month). Cross-repo coordination tax is highest exactly when interfaces are changing — a monorepo lets a boundary change land in one atomic commit.
- **One `CLAUDE.md`, one context** for Claude Code; it sees both sides when wiring the integration.
- The **standalone-task-tracker** property is preserved by the *package* boundary (clean public interface, no reaching into goal-bot), not by physical repo separation.
- **Direction of difficulty:** extracting a clean package into its own repo later is cheap; merging two entangled repos later is painful. Keep the cheap option open.
Databases stay **separate schemas on one Postgres instance** (already decided) — that independence is at the *data* layer and is orthogonal to repo layout.
 
→ This is **ADR-0002** material (see §4). Recorded as a recommendation, not a fait accompli — your call.
 
---
 
## 3. Folder structure (target)
 
```
agency-agent/                     ← monorepo root ("an agent to develop agency")
├─ README.md                      ← what this is, how to run, where docs live
├─ CLAUDE.md                      ← Claude Code operating context (a map, not a manual)
├─ .claude/
│  └─ rules/
│     ├─ adrs.md                  ← "need a past decision? read doc/decisions/index.md FIRST"
│     └─ …                        ← further modular rules as patterns emerge
├─ doc/
│  ├─ glossary.md                 ← canonical vocabulary (95% Floor, chapter, rotation, …)
│  ├─ product/
│  │  ├─ vision.md                ← objectives, the 95% Floor philosophy, psychology stance
│  │  └─ behavior-spec.md         ← daily ritual, needs/wants, carry-over, smart-subset, shared goals
│  ├─ architecture/
│  │  ├─ architecture.md          ← identity/task↔goal/package/MCP boundary (chat I; v0.3)
│  │  ├─ data-model.md            ← schema (from spec §6) + the load-bearing/soft map
│  │  ├─ mcp-tools.md             ← the MCP tool surface (minimum set)
│  │  └─ integration.md           ← task-tracker ↔ goal-bot boundary (chat I output)
│  ├─ research/
│  │  ├─ psychology.md            ← findings (chat R1)
│  │  ├─ competitive.md           ← findings (chat R2)
│  │  └─ decision-logging.md      ← ADR-practice findings (chat R3, small)
│  ├─ templates/
│  │  └─ goal-markdown.md         ← ingestion template + inferred-vs-typed contract (chat T)
│  ├─ decisions/                  ← ADRs, append-only
│  │  ├─ index.md                 ← ADR status board; updated with every new/superseded ADR
│  │  ├─ 0001-recap-of-settled-decisions.md
│  │  ├─ 0002-monorepo-with-packages.md
│  │  ├─ 0003-separate-schemas-one-instance.md
│  │  └─ …
│  └─ build/
│     └─ mvp-plan.md              ← sequencing + cut line for implementation
└─ packages/
   ├─ profile/                    ← identity (profile/person/group) + Tier-1 authored profile; deps: none
   ├─ task-tracker/               ← deployable standalone (tasks without goals); deps: profile
   └─ goal-bot/                   ← goal domain + goal MCP + Tier-2/3 goal memory; deps: profile, task-tracker
                                  ←   hosts agent-runtime loop + composition entrypoint as INTERNAL
                                  ←   modules for MVP (clean module line; extractable later — ADR-0014)
```
 
> **Standalone deploy** = `profile` + `task-tracker` (no goal-bot, no goal concept). The `agent`/`app` packages from doc/_archive/architecture.md v0.3 are folded into goal-bot as internal modules for MVP and are *not* separate package directories yet (ADR-0014).
 
---
 
## 4. Conventions
 
### 4a. ADRs (Architecture Decision Records) — append-only
- **Format:** Nygard-style, lightweight. Each ADR: `# ADR-NNNN: <title>` then **Status**, **Context**, **Decision**, **Consequences**. One decision per file.
- **Statuses:** `Proposed` → `Accepted` → (later) `Superseded by ADR-XXXX` or `Deprecated`. 
- **Append-only rule:** never rewrite the substance of an accepted ADR. To change a decision, write a *new* ADR and set the old one's status line to `Superseded by ADR-XXXX`. The only edit ever made to an existing ADR is that status line. This gives a truthful decision history — same spirit as goal-version pinning.
- **Numbering:** zero-padded, monotonic. `doc/decisions/0007-….md`.
- **Index (`doc/decisions/index.md`).** A status board — a table of every ADR: number, title, status, and supersedes / superseded-by links. It is **the entry point**: you read the index to find the right ADR, never the raw directory listing. Updated in the *same commit* as any new or superseded ADR, so it never lags. A new ADR is not "done" until the index reflects it.
- **Seed set to write in Phase 0** (capturing what we've already settled, so nothing relies on chat memory):
  - 0001 — Recap of settled decisions (the 95% Floor; morning-only ritual; need/want = goal-definition property with coexisting levels; identity-by-ID + tags; chapters; completion-advanced rotation; version pinning; three-tier memory; 6a day boundary; orthogonal goal-type attributes).
  - 0002 — Monorepo with package boundaries (§2).
  - 0003 — Separate Postgres schemas on one instance; integration boundary, not merged model.
- **Note:** R3 will sanity-check this convention against current practice (MADR vs. Nygard, tooling like `adr-tools`); if it suggests a tweak, that's itself an ADR. We start logging immediately rather than waiting on the research.
### 4b. Glossary
- One file, `doc/glossary.md`. Every coined term gets a one-line canonical definition + a pointer to the doc that owns its full treatment. If a term's meaning changes, the glossary changes and an ADR records why.
- Seed terms: 95% Floor, chapter, rotation (completion-advanced), need / want, minimum bar / stretch, quota, interval, fixed_schedule, the three tiers (authored profile / observations / insight digest), lock-in, carry-over, lighter-day nudge, friction log, win log.
### 4c. CLAUDE.md (repo root)
- Orients Claude Code on every session: what the project is (1 paragraph), the package map, **pointers to the canonical docs** (don't restate them), the conventions above, and the non-negotiables (privacy, the human-approval boundary for Tier-1 profile writes, never-auto-drop, etc.).
- Keep it a **map, not a manual** — it routes to docs rather than duplicating them, so it doesn't drift.
### 4d. Doc versioning
- Product/architecture docs carry a small `vX.Y` + status header. Substantive changes bump the version; the *why* lives in an ADR, not in the doc's prose.
---
 
## 5. Workstream chats → output docs
 
Each kickoff chat is **self-contained**: it states its role, takes the goal-bot spec (in project knowledge) as input, produces **one** artifact, and stops. Five kickoff prompts now; MCP-tools spec follows once its inputs settle.
 
| Chat | Produces | Key inputs | Depends on | Stops when |
|---|---|---|---|---|
| **R1 — Psychology research** | `research/psychology.md` | spec | — | findings mapped to *our* design decisions |
| **R2 — Competitive/tools research** | `research/competitive.md` | spec | — | borrowable ideas + anti-patterns, mapped to our scope |
| **R3 — Decision-logging practice** (small) | `research/decision-logging.md` | §4a | — | recommends/confirms our ADR convention |
| **T — Goal-markdown template** | `templates/goal-markdown.md` | spec §3–§6 | data-model stable (it is) | template + inferred-vs-typed contract defined |
| **I — Integration boundary** | `architecture/integration.md` | spec §6 + **task-tracker schema** | task-tracker schema available | cross-schema query patterns + shared conventions defined |
| *(later)* **M — MCP tools spec** | `architecture/mcp-tools.md` | data-model + I | I done | minimum tool set specced |
 
**I's input:** task-tracker schema, supplied either by the chat introspecting via the task-tracker MCP, or you pasting the SQL dumps. Either works.
 
---
 
## 6. Phased sequencing (dependency-aware)
 
```
Phase 0 — Scaffold        repo skeleton · doc/ structure · CLAUDE.md · glossary stub
(this plan + setup)       · ADRs 0001–0003 · add spec v0.4 to project knowledge
 
Phase 1 — Parallelize     ┌─ R1 psychology ─┐
(nothing blocks here)     ├─ R2 competitive ┤   …and concurrently…  decompose master
                          └─ R3 adr-practice┘                       spec → product/ + data-model
 
Phase 2 — Converge        fold research → product decisions (new ADRs for any changes)
(downstream of research)  → draft T (template) · draft I (integration) → then M (mcp-tools)
                          → write build/mvp-plan.md
 
Phase 3 — Build           repo + finalized docs + CLAUDE.md drive Claude Code
                          VPS + Postgres setup · implement per mvp-plan
```
 
**The one dependency to respect:** research (R1/R2) is *upstream* of finalizing product + schema. Draft the template and integration from v0.4 now, but expect a revision pass after research lands — don't treat them as frozen until Phase 2 closes.
 
---
 
## 7. Decisions needed to start Phase 0
 
**Resolved (structural pass):**
- **Repo** ✅ monorepo-with-packages confirmed (ADR-0002, Accepted); MVP = three packages (ADR-0014).
- **§5 goal-category calls** ✅ `interval`, `fixed_schedule`, `accumulation`, `paused` all **IN**; `scale`/rating out. **Jade's gym = `quota`.** (chat-T; spec §5.)
- **OQ-16** ✅ **dissolved** — shared goals are group-profile-owned and follow normal recurrence semantics (D-17 / ADR-0012).
**Still needed:**
- **Task-tracker schema for I:** MCP introspection vs. SQL dump. *(I is now substantially covered by doc/_archive/architecture.md v0.3; this is the remaining input detail.)*
None of these block writing the kickoff prompts — they just need to be settled before the corresponding *chat* runs.
 
---
 
## 8. How this drives Claude Code (the payoff)
 
When Phase 3 starts, the repo is the whole brief: `CLAUDE.md` routes to canonical docs, the ADRs explain *why* every structural choice was made, the glossary fixes vocabulary, `data-model.md` + `mcp-tools.md` + `integration.md` specify the build, and `build/mvp-plan.md` orders it. Claude Code inherits a project where the thinking is already externalized and consistent — which is the entire point of doing the spec work in this interface first.
 
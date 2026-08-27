# Task Tracker MCP Server — Specification

## Overview

An MCP server that provides persistent **personal** task and daily-log tracking for a Claude Project used for daily productivity management. Replaces the earlier system where tasks lived in daily markdown artifacts and were manually carried forward between chat sessions (lossy, error-prone).

**Personal-only (ADR-0019).** The tracker once carried a parallel work half — work tasks, sprints, ODS tickets, JN-bucket time entries for timecards. Work tracking now lives in a separate work assistant outside this repo; the work tables, tools, and fields were removed (migration 0007). The archival work history stays in the legacy standalone repo's SQLite (`~/dev/task-tracker-mcp`).

The MCP server exposes tools that Claude calls during conversation. The daily markdown tracker artifact continues to exist as a rendered view of the database — same format, same utility, but no longer the source of truth.

## Architecture

- MCP server exposes tools for Claude to read/write tasks and daily logs
- **Postgres** `tasktracker` schema on the shared monorepo instance (ADR-0008); rows are person-stamped via `owner_id` (ADR-0004). SQLite adapters are retained for standalone/local use.
- **Clean architecture**: domain (entities, entity factories), application (ports, use cases), infrastructure (adapters, MCP API routes)
- **Dependency inversion**: repository interfaces defined as ports in the application layer, Postgres implementation as an infrastructure adapter.
- **Pydantic** is the one third-party exception permitted in all layers (validation, serialization)

**Style:** PEP 8 throughout. Clean architecture component names should be explicit about their role:
- Entities: `PersonalTaskEntity`, `DailyLogEntity`, etc.
- Ports (interfaces): `TaskRepositoryPort`, `DailyLogRepositoryPort`, etc.
- Use cases: `CreateTaskUseCase`, `CompleteTaskUseCase`, etc.
- Adapters: `PgTaskRepositoryAdapter`, `SqliteTaskRepositoryAdapter`, etc.
- Factories: `PersonalTaskFactory`, etc.

No ambiguity about what layer a component belongs to from its name alone.

**SDK:** Python with `fastmcp`. Fall back to base `mcp` SDK if fastmcp lacks required features.

**Two server surfaces (ADR-0018):** `create_app()` (`python -m task_tracker`) is the full personal server. `create_shared_app()` (`python -m task_tracker --shared`) is a read-only surface for bots other people can talk to: it grants only `get_task_detail`, `get_open_tasks`, `search_tasks`, `get_tasks_updated_on`, backed by a repository that adds `private = false` to every task read at the SQL layer (including child-task loads). Privacy is enforced by which server a bot's MCP config mounts — never by prompts or client-side tool filtering. goal-bot itself never mounts either server; it reads through the typed `TaskQueryClient` port (ADR-0007), which applies the same private filter.

**Testing:** `pytest`. Claude Code should write and run tests during development.

**Linting & Formatting:** `ruff`. PEP 8 enforced via `ruff check .` and `ruff format .`. Configure in `pyproject.toml`. The linter is authoritative for style — no additional style rules in CLAUDE.md or code comments.

## Tool Design Philosophy

**Composite queries for reads, specific tools for mutations.**

- Morning kickoff should be 1 call (`get_tracker_data()`) not 5 separate queries. Reads are consolidated into composite endpoints that return everything Claude needs for a given workflow.
- Mutations are specific and precise: `complete_task()`, `nuke_task()`. One action per call.
- Granular read tools exist only when they serve a workflow `get_tracker_data()` doesn't cover (ad-hoc queries, stale-item reviews, day cross-checks). Blocked tasks, deadlines, and commitments are all surfaced by the composite query — no dedicated tools needed.
- This minimizes the number of tool-selection decisions Claude makes while keeping writes unambiguous.

**Tool descriptions are the primary interface for Claude's tool selection.** Every tool must have a rich description and parameter docstrings baked into the server code. These descriptions are Claude's first and most reliable source of guidance for when and how to use each tool. The descriptions live in the tool modules (`src/task_tracker/tools/`); they are the implementation of record.

## Database Schema

Postgres `tasktracker` schema (migrations 0003–0007). Column types below use the Postgres forms (`bigint GENERATED ALWAYS AS IDENTITY`, `timestamptz`, `double precision`); the retained SQLite schema mirrors them with SQLite types.

### `personal_tasks`

Personal items across all tiers — deadlines, errands, projects, deferred dreams.

| Column | Type | Notes |
|--------|------|-------|
| id | bigint identity PK | |
| owner_id | bigint NOT NULL | FK → profile.person(profile_id). Person-stamping (ADR-0004). |
| title | text NOT NULL | |
| tier | integer | 1, 2, or 3. See tier definitions below. |
| status | text | "not_started", "in_progress", "blocked", "waiting", "done", "nuked" |
| blocked_reason | text | Nullable. |
| deadline | date | Nullable. Hard deadline if one exists. |
| parent_task_id | bigint | Nullable FK → personal_tasks.id. One level of nesting only. |
| is_commitment | boolean | Default false. |
| commitment_notes | text | Nullable. Freeform. |
| priority_rank | integer | Nullable. Relative ordering **scoped to tier**. |
| pinned | boolean | Default false. Pinned Tier 3 items appear in the "what this is all for" tracker section. |
| private | boolean | Default false. Invisible to goal-bot and to the shared task surface (ADR-0018) — never a goal candidate, never referenceable, `get_task_status` answers None. Prospective only: flipping it retracts nothing already ingested. Full personal tracker unaffected. |
| notes | text | Rich notes — returned only by detail endpoints. |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| completed_at | timestamptz | Nullable |
| deleted_at | timestamptz | Nullable. Soft delete. |

**Tier definitions:**
- **Tier 1**: External forcing function — hard deadlines, travel dates, blockers that cascade
- **Tier 2**: Important and wanted, but no one's holding me to it
- **Tier 3**: Someday/maybe projects — things I care about but can't justify prioritizing yet

**Note:** `days_carried` is NOT stored. Computed at query time as days since `created_at`. See [Days Carried & Staleness](#days-carried--staleness).

### `daily_logs`

One row per person per day (PK `(owner_id, date)`). Whoop data, structured EOD reflections, Claude's observations.

| Column | Type | Notes |
|--------|------|-------|
| owner_id | bigint | FK → profile.person(profile_id). Part of PK. |
| date | date | Part of PK. |
| whoop_recovery | integer | Nullable. Percentage (0-100). |
| whoop_hrv | integer | Nullable. |
| whoop_sleep_hours | double precision | Nullable. |
| whoop_rhr | integer | Nullable. |
| reflection_moved_forward | text | Nullable. What moved forward today — completions, partial progress, decisions, agency moments. |
| reflection_didnt_move | text | Nullable. What didn't move and why — blockers vs. choices. |
| reflection_do_differently | text | Nullable. What would I do differently — learning extraction. |
| reflection_protect_tomorrow | text | Nullable. One thing to protect tomorrow — implementation intention. |
| observations | text | Nullable. Claude's momentum/pattern notes — streaks, correlations, trajectory observations. Written at EOD, read at next morning kickoff for continuity. |
| notes | text | Nullable. General day context. |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### `system_meta`

Key-value store for system-level state that doesn't belong to a specific entity.

| Column | Type | Notes |
|--------|------|-------|
| key | text PK | e.g. "last_tier3_review" |
| value | text | Stored as text, parsed by consumer. |
| updated_at | timestamptz | |

**Initial keys:**
- `last_tier3_review` — DATE string. Used by `get_tracker_data()` to compute `tier3_review_due` (true if 90+ days since last review or never reviewed).

## Days Carried & Staleness

Both `days_carried` and staleness use `created_at` as the reference point. Computed at query time, not stored.

- **`days_carried`** = days since `created_at` for any open (non-done, non-nuked, non-deleted) task. Returned by `get_open_tasks()` and `get_tracker_data()`.
- **Stale** = open task where `days_carried` ≥ threshold (default 30). Surfaced on Mondays via `get_tracker_data()` or on demand via `get_open_tasks(min_days_open=30)`.

Rationale: tasks only enter this system when they become relevant. If something has been in the system 30+ days and isn't done, it deserves a "still earning its place?" check — regardless of whether status has changed.

## MCP Tools

Authoritative descriptions and parameter docstrings live in the tool modules (`src/task_tracker/tools/`). Summary:

### Task CRUD

- **`create_task(fields...)`** — Create a single personal task (title, tier?, status?, deadline?, parent_task_id?, is_commitment?, commitment_notes?, priority_rank?, pinned?, private?, notes?).
- **`create_tasks(tasks: list)`** — Batch create. For brain dumps (4-8 items at once). A legacy `type` key in an item is tolerated and ignored.
- **`get_task_detail(id)`** — Full detail for one task including rich notes. Children returned with full detail.
- **`update_task(id, fields...)`** — Update any field(s).
- **`batch_update_tasks(updates: list)`** — Batch update for EOD sweeps and tier reorgs. Each item is `{id, ...fields}`.
- **`complete_task(id)`** — Shorthand: status=done, completed_at=now.
- **`nuke_task(id)`** — Status=nuked. Not completed, just dropped. Data preserved.
- **`delete_task(id)`** — Soft delete (sets deleted_at). For mistakes/duplicates.
- **`restore_task(id)`** — Undelete: clears `deleted_at`. Reverse of `delete_task`. No-op (returns current record) if the task isn't soft-deleted; null if no such task.

### Task Queries

- **`get_open_tasks(min_days_open?: int)`** — All non-done, non-nuked, non-deleted tasks as a flat list of parents (children nested inline, one level). Optional `min_days_open` filters to tasks with `days_carried` ≥ threshold (7-day weekly review, 30-day monthly stale review). LIGHTWEIGHT fields — no rich notes.
- **`get_tasks_updated_on(target_date)`** — Tasks with status changes or notes updated on a date. Flat list, includes tasks in any non-deleted status (a task completed yesterday is relevant). Lightweight fields.
- **`search_tasks(query, include_done?, include_deleted?, limit?)`** — Keyword search over `title` + `notes`. Returns ranked lightweight rows (id, title, tier, status); title matches rank above notes-only matches. Currently a case-insensitive `LIKE` implementation (see TODO.md for the FTS graduation). Excludes done and soft-deleted by default. Keyword, not semantic — zero-token-overlap synonyms are missed; handle at call time by searching synonyms or falling back to `get_open_tasks()`.

### Composite Queries

- **`get_tracker_data()`** — Single call returning everything needed to generate a daily tracker artifact. Response payload:
  - **`personal`**: Open tasks (same lightweight fields and nesting as `get_open_tasks()`, plus computed annotations: `is_stale`, `is_blocked` (true when status is `blocked` or `waiting`), `has_upcoming_deadline`). Claude filters and groups to build tracker sections, and uses `pinned` to build the Tier 3 motivational section.
  - **`daily_log`**: Today's daily_log if exists (whoop data, previous observations).
  - **`tier3_review_due`**: boolean, true if 90+ days since `system_meta.last_tier3_review` or never reviewed.

### Daily Logs

- **`log_daily(target_date, whoop_recovery?, whoop_hrv?, whoop_sleep_hours?, whoop_rhr?, notes?)`** — Create/update daily log.
- **`log_reflection(target_date, moved_forward?, didnt_move?, do_differently?, protect_tomorrow?, observations?)`** — Set/update structured EOD reflection and Claude's observations. All fields optional for partial updates.
- **`get_daily_log(target_date)`** — Single date.
- **`get_daily_logs(start_date, end_date)`** — Date range for pattern analysis.

### System Meta

- **`set_meta(key, value)`** — Write a system_meta value. Read is handled server-side by `get_tracker_data()`.

### Date / Time

- **`get_time(timezone?)`** — Current date, time, day of week, and UTC offset. Defaults to `America/Los_Angeles` (PT) when `timezone` is omitted; override with any IANA timezone string. Use at the start of a session to orient on date-sensitive operations (deadlines, daily log entries).

## Personal Task Statuses

| Status | Meaning |
|--------|---------|
| not_started | On the list, no action taken |
| in_progress | Actively being worked on |
| blocked | External dependency preventing progress. blocked_reason set. |
| waiting | Externally dependent, nothing to do (e.g. "ball in their court"). Distinct from blocked. |
| done | Completed |
| nuked | Explicitly dropped. Data preserved. |

## Tracker Artifact Relationship

- Claude still generates a daily markdown tracker artifact in the same format Matthew is used to
- The artifact is a **rendered view** of the database, generated from `get_tracker_data()`
- The artifact is NOT the source of truth — the database is
- Tasks cannot be lost between sessions because they persist in the DB
- **Pinned Tier 3 items** appear in a "what this is all for" section — motivational, not a to-do list. Matthew controls which items are pinned via `update_task()`.

## Not In Scope (for now)
- Work tracking of any kind — work tasks, sprints, time entries, timecards, estimation accuracy (removed by ADR-0019; lives in a separate work assistant)
- Habit tracking (guitar practice streaks, etc.)
- Whoop API integration (door is open via daily_logs schema)
- Notification system
- Semantic / embedding-based search (keyword `search_tasks` ships now; FTS and beyond tracked in TODO.md)
- Integration with transcript summarizer

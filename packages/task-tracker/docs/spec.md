# Task Tracker MCP Server — Specification

## Overview

An MCP server that provides persistent task and time tracking for a Claude Project used for daily productivity management. Replaces the current system where tasks live in daily markdown artifacts and are manually carried forward between chat sessions (lossy, error-prone).

The MCP server exposes tools that Claude calls during conversation. The daily markdown tracker artifact continues to exist as a rendered view of the database — same format, same utility, but no longer the source of truth.

## Architecture

**Option C**: MCP server for Claude + shared SQLite database.

- MCP server exposes tools for Claude to read/write tasks and time entries
- SQLite database in a known filesystem location so external scripts can query it independently
- **Clean architecture**: domain (entities, entity factories), application (ports, use cases), infrastructure (adapters, MCP API routes)
- **Dependency inversion**: repository interfaces defined as ports in the application layer, SQLite implementation as an infrastructure adapter. Swapping to Postgres later changes nothing above the infrastructure layer.
- **Pydantic** is the one third-party exception permitted in all layers (validation, serialization)
- Runs locally initially, will port to VPS once stable

**Style:** PEP 8 throughout. Clean architecture component names should be explicit about their role:
- Entities: `WorkTaskEntity`, `PersonalTaskEntity`, `SprintEntity`, etc.
- Ports (interfaces): `TaskRepositoryPort`, `TimeEntryRepositoryPort`, etc.
- Use cases: `CreateTaskUseCase`, `CompleteTaskUseCase`, etc.
- Adapters: `SqliteTaskRepositoryAdapter`, `SqliteTimeEntryRepositoryAdapter`, etc.
- Factories: `WorkTaskFactory`, `PersonalTaskFactory`, etc.

No ambiguity about what layer a component belongs to from its name alone.

**SDK:** Python with `fastmcp`. Fall back to base `mcp` SDK if fastmcp lacks required features.

**Two server surfaces (ADR-0018):** `create_app()` (`python -m task_tracker`) is the full personal server. `create_shared_app()` (`python -m task_tracker --shared`) is a read-only surface for bots other people can talk to: it grants only `get_task_detail`, `get_open_tasks`, `search_tasks`, `get_tasks_updated_on`, backed by a repository that adds `private = false` to every personal-task read at the SQL layer (including child-task loads). Privacy is enforced by which server a bot's MCP config mounts — never by prompts or client-side tool filtering. goal-bot itself never mounts either server; it reads through the typed `TaskQueryClient` port (ADR-0007), which applies the same private filter.

**Testing:** `pytest`. Claude Code should write and run tests during development.

**Linting & Formatting:** `ruff`. PEP 8 enforced via `ruff check .` and `ruff format .`. Configure in `pyproject.toml`. The linter is authoritative for style — no additional style rules in CLAUDE.md or code comments.

## Tool Design Philosophy

**Composite queries for reads, specific tools for mutations.**

- Morning kickoff should be 1 call (`get_tracker_data()`) not 5 separate queries. Reads are consolidated into composite endpoints that return everything Claude needs for a given workflow.
- Mutations are specific and precise: `complete_task()`, `nuke_task()`, `log_time()`. One action per call.
- Granular read tools exist only when they serve a workflow `get_tracker_data()` doesn't cover (ad-hoc queries, sprint reviews, standup cross-checks). Blocked tasks, deadlines, and commitments are all surfaced by the composite query — no dedicated tools needed.
- This minimizes the number of tool-selection decisions Claude makes while keeping writes unambiguous.

**Tool descriptions are the primary interface for Claude's tool selection.** Every tool must have a rich description and parameter docstrings baked into the server code. These descriptions are Claude's first and most reliable source of guidance for when and how to use each tool. See [Tool Descriptions & Docstrings](#tool-descriptions--docstrings) for the exact text to implement.

## Database Schema

### `work_tasks`

Work items including sprint tickets, backlog items, PR reviews, admin tasks, etc.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| title | TEXT NOT NULL | Short description |
| ods_ticket | TEXT | Nullable. e.g. "ODS-4484". Many work tasks don't have tickets. |
| sprint_id | TEXT | Nullable. FK → sprints.id |
| commitment_level | TEXT | "sprint_committed", "sprint_stretch", "backlog" |
| jn_bucket | TEXT | "planning", "development", "sustaining", "overhead", "training" |
| status | TEXT | "not_started", "in_progress", "in_review", "blocked", "waiting", "done", "delegated", "nuked" |
| blocked_reason | TEXT | Nullable. Why it's blocked. |
| estimate_hours | REAL | Nullable. Original estimate in hours. |
| deadline | DATE | Nullable. Task-level hard deadline (e.g. "PR due Friday", "customer demo Wednesday"). Distinct from sprint end date. |
| parent_task_id | INTEGER | Nullable FK → work_tasks.id. One level of nesting only. |
| is_commitment | BOOLEAN | Default false. True when an explicit promise has been made. |
| commitment_notes | TEXT | Nullable. Freeform — who, when, context. |
| priority_rank | INTEGER | Nullable. Relative ordering **scoped to commitment_level**. Rank 1 in sprint_committed and rank 1 in backlog are independent. |
| notes | TEXT | Detailed notes — context, blockers, decisions, history. Returned only by detail endpoints, not list endpoints. |
| created_at | DATETIME | Auto-set |
| updated_at | DATETIME | Auto-updated on any field change |
| completed_at | DATETIME | Nullable. Set when status → done |
| deleted_at | DATETIME | Nullable. Soft delete. Filtered out by default on all queries. |

**Note:** `actual_hours` is NOT stored. Computed by summing `time_entries.duration_minutes` for the task.

**Note:** `days_carried` is NOT stored. Computed at query time as days since `created_at`. See [Days Carried & Staleness](#days-carried--staleness).

### `personal_tasks`

Personal items across all tiers — deadlines, errands, projects, deferred dreams.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| title | TEXT NOT NULL | |
| tier | INTEGER | 1, 2, or 3. See tier definitions below. |
| status | TEXT | "not_started", "in_progress", "blocked", "waiting", "done", "nuked" |
| blocked_reason | TEXT | Nullable. |
| deadline | DATE | Nullable. Hard deadline if one exists. |
| parent_task_id | INTEGER | Nullable FK → personal_tasks.id. One level of nesting only. |
| is_commitment | BOOLEAN | Default false. |
| commitment_notes | TEXT | Nullable. Freeform. |
| priority_rank | INTEGER | Nullable. Relative ordering **scoped to tier**. |
| pinned | BOOLEAN | Default false. Pinned Tier 3 items appear in the "what this is all for" tracker section. |
| private | BOOLEAN | Default false. Invisible to goal-bot and to the shared task surface (ADR-0018) — never a goal candidate, never referenceable, `get_task_status` answers None. Prospective only: flipping it retracts nothing already ingested. Full personal tracker unaffected. |
| notes | TEXT | Rich notes — returned only by detail endpoints. |
| created_at | DATETIME | |
| updated_at | DATETIME | |
| completed_at | DATETIME | Nullable |
| deleted_at | DATETIME | Nullable. Soft delete. |

**Tier definitions:**
- **Tier 1**: External forcing function — hard deadlines, travel dates, blockers that cascade
- **Tier 2**: Important and wanted, but no one's holding me to it
- **Tier 3**: Someday/maybe projects — things I care about but can't justify prioritizing yet

**Note:** `days_carried` computed from `created_at`, same as work tasks.

### `time_entries`

Linked to work_tasks only. Personal tasks do not get time tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| work_task_id | INTEGER NOT NULL | FK → work_tasks.id |
| date | DATE NOT NULL | The day this time was logged |
| duration_minutes | INTEGER NOT NULL | |
| jn_bucket | TEXT NOT NULL | May differ from the task's default bucket. |
| notes | TEXT | Nullable. What happened during this block. |
| created_at | DATETIME | |

### `sprints`

Lightweight grouping for sprint-based queries.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | Sprint end date, e.g. "2026-03-03" |
| start_date | DATE | |
| end_date | DATE | |
| status | TEXT | "active", "completed" |
| notes | TEXT | Nullable. Retro notes, themes. |

### `daily_logs`

One row per day. Whoop data, structured EOD reflections, Claude's observations.

| Column | Type | Notes |
|--------|------|-------|
| date | DATE PRIMARY KEY | |
| whoop_recovery | INTEGER | Nullable. Percentage (0-100). |
| whoop_hrv | INTEGER | Nullable. |
| whoop_sleep_hours | REAL | Nullable. |
| whoop_rhr | INTEGER | Nullable. |
| reflection_moved_forward | TEXT | Nullable. What moved forward today — completions, partial progress, decisions, agency moments. |
| reflection_didnt_move | TEXT | Nullable. What didn't move and why — blockers vs. choices. |
| reflection_do_differently | TEXT | Nullable. What would I do differently — learning extraction. |
| reflection_protect_tomorrow | TEXT | Nullable. One thing to protect tomorrow — implementation intention. |
| observations | TEXT | Nullable. Claude's momentum/pattern notes — streaks, correlations, trajectory observations. Written at EOD, read at next morning kickoff for continuity. |
| notes | TEXT | Nullable. General day context. |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### `system_meta`

Key-value store for system-level state that doesn't belong to a specific entity.

| Column | Type | Notes |
|--------|------|-------|
| key | TEXT PRIMARY KEY | e.g. "last_tier3_review" |
| value | TEXT | Stored as text, parsed by consumer. |
| updated_at | DATETIME | |

**Initial keys:**
- `last_tier3_review` — DATE string. Used by `get_tracker_data()` to compute `tier3_review_due` (true if 90+ days since last review or never reviewed).

## Days Carried & Staleness

Both `days_carried` and staleness use `created_at` as the reference point. Computed at query time, not stored.

- **`days_carried`** = days since `created_at` for any open (non-done, non-nuked, non-deleted) task. Returned by `get_open_tasks()` and `get_tracker_data()`.
- **Stale** = open task where `days_carried` ≥ threshold (default 30). Surfaced on Mondays via `get_tracker_data()` or on demand via `get_open_tasks(min_days_open=30)`.

Rationale: Matthew's Jira backlog is separate. Tasks only enter this system when they become relevant. If something has been in the system 30+ days and isn't done, it deserves a "still earning its place?" check — regardless of whether status has changed.

## JN Bucket Rules (for time_entries)

- **Planning**: Sprint management, estimation, Jira, backlog pruning, architecture, ADRs
- **Development**: Feature work, dev help/unblocking, PR reviews (default)
- **Sustaining**: Customer work, bugs, bugfixes, maintenance. PR reviews here ONLY if the PR is for a bug or maintenance.
- **Overhead**: 1:1s, standups, team meetings, 360 feedback, self-evals, admin, timecards, emails
- **Training**: Learning, reading, courses

## MCP Tools

### Task CRUD

- **`create_task(type, fields...)`** — Create a single task.
- **`create_tasks(tasks: list)`** — Batch create. For brain dumps (4-8 items at once).
- **`get_task_detail(id, type)`** — Full detail for one task including rich notes and `actual_hours` (computed from time_entries, work tasks only). Children returned with full detail.
- **`update_task(id, type, fields...)`** — Update any field(s).
- **`batch_update_tasks(updates: list)`** — Batch update for EOD sweeps, sprint reassignments, tier reorgs.
- **`complete_task(id, type)`** — Shorthand: status=done, completed_at=now.
- **`nuke_task(id, type)`** — Status=nuked. Not completed, just dropped. Data preserved.
- **`delete_task(id, type)`** — Soft delete (sets deleted_at). For mistakes/duplicates.
- **`restore_task(id, type)`** — Undelete: clears `deleted_at`. Reverse of `delete_task`. No-op (returns current record) if the task isn't soft-deleted; null if no such task.

### Task Queries

- **`get_open_tasks(type?: "work"|"personal"|"all", min_days_open?: int)`** — All non-done, non-nuked, non-deleted tasks. Optional `min_days_open` filters to tasks with `days_carried` ≥ threshold (useful for 7-day personal item prompts, Monday 30-day stale reviews). Returns nested structure (parent tasks include children inline, one level — children do not appear separately as top-level items). LIGHTWEIGHT fields — work: id, title, ods_ticket, sprint_id, commitment_level, jn_bucket, status, blocked_reason, estimate_hours, deadline, days_carried, is_commitment, commitment_notes, priority_rank, parent_task_id. Personal: id, title, tier, status, blocked_reason, deadline, days_carried, is_commitment, commitment_notes, priority_rank, pinned, parent_task_id. No rich notes.
- **`get_sprint_tasks(sprint_id?)`** — All tasks for a sprint (default: active). Includes done, nuked, waiting, and delegated tasks for sprint-in-progress visibility and transparency. Excludes soft-deleted. Returns: id, title, ods_ticket, status, commitment_level, estimate_hours, actual_hours (computed), priority_rank, completed_at. No rich notes.
- **`get_tasks_updated_on(date)`** — Tasks with status changes, time logged, or notes updated on a date. Optional standup cross-check. Returns flat list (no nesting), includes tasks in any non-deleted status (including done/nuked, since a task completed yesterday is relevant). Same lightweight fields as `get_open_tasks()` per type.
- **`search_tasks(query, include_done?, include_deleted?, limit?)`** — Keyword search over `title` + `notes` across work and personal tasks. Returns ranked lightweight rows (id, title, tier, status, type); title matches rank above notes-only matches. Currently a `LIKE` implementation (see TODO.md for the FTS5 graduation). Excludes done and soft-deleted by default. Keyword, not semantic — zero-token-overlap synonyms are missed; handle at call time by searching synonyms or falling back to `get_open_tasks()`.
- **`get_estimation_accuracy(n?, type?)`** — Estimate-vs-actual analysis for completed work tasks. Returns per-task rows (title, estimate_hours, actual_hours, ratio = actual/estimate) plus aggregate median ratio. `n` caps to the most-recent N completed; `type` filters by task type. Work-only: personal tasks carry neither estimates nor time entries, so `type='personal'` returns no rows.

### Composite Queries

- **`get_tracker_data()`** — Single call returning everything needed to generate a daily tracker artifact. Response payload:
  - **`work`**: Open work tasks (same lightweight fields and nesting as `get_open_tasks()`, plus computed annotations: `is_stale`, `is_blocked` (true when status is `blocked` or `waiting`), `has_upcoming_deadline`). Claude filters and groups to build tracker sections.
  - **`personal`**: Open personal tasks (same lightweight fields and nesting as `get_open_tasks()`, plus same computed annotations). Claude uses `pinned` field to build the Tier 3 motivational section.
  - **`sprint`**: Active sprint info (id, start/end dates, status) + all sprint tasks including done and nuked (same fields as `get_sprint_tasks()`).
  - **`daily_log`**: Today's daily_log if exists (whoop data, previous observations).
  - **`tier3_review_due`**: boolean, true if 90+ days since `system_meta.last_tier3_review` or never reviewed.

### Time Tracking

- **`log_time(work_task_id, date, duration_minutes, jn_bucket, notes?)`** — Log a time entry.
- **`delete_time_entry(time_entry_id)`** — Hard-delete a mis-logged time entry. Returns the removed row (date, bucket, minutes, work_task_id, notes) so it can be confirmed. Hard delete (not soft) — a wrong time entry has no analytic value. Null if no such entry.
- **`get_timecard(start_date, end_date)`** — Aggregate by date + jn_bucket. Includes ODS ticket references.
- **`get_time_gaps(start_date, end_date)`** — Per-day logged time vs ~8h expected. Flags gaps for timecard uncertainty notes.

### Daily Logs

- **`log_daily(date, whoop_recovery?, whoop_hrv?, whoop_sleep_hours?, whoop_rhr?, notes?)`** — Create/update daily log.
- **`log_reflection(date, moved_forward?, didnt_move?, do_differently?, protect_tomorrow?, observations?)`** — Set/update structured EOD reflection and Claude's observations. All fields optional for partial updates.
- **`get_daily_log(date)`** — Single date.
- **`get_daily_logs(start_date, end_date)`** — Date range for pattern analysis.

### Sprint Management

- **`set_active_sprint(sprint_id, start_date?, end_date?)`** — Creates if needed, marks active, deactivates previous.

### System Meta

- **`set_meta(key, value)`** — Write a system_meta value. Read is handled server-side by `get_tracker_data()`.

### Date / Time

- **`get_time(timezone?)`** — Current date, time, day of week, and UTC offset. Defaults to `America/Los_Angeles` (PT) when `timezone` is omitted; override with any IANA timezone string. Use at the start of a session to orient on date-sensitive operations (sprint boundaries, deadlines, daily log entries).

## Tool Descriptions & Docstrings

These are the exact descriptions and parameter docstrings to implement in the MCP server code. They are Claude's primary interface for tool discovery and selection. Every tool description specifies: when to use it, what it expects, and what it returns. Mutation tools include routing guidance so Claude picks the right one without external reference.

### Task CRUD

**`create_task`**
```
description: "Create a single work or personal task. Use when Matthew mentions a new task, ticket, or item to track. For multiple tasks at once (brain dumps, sprint planning), use create_tasks instead."
params:
  type: "Task type: 'work' or 'personal'"
  title: "Short task description"
  ods_ticket: "ODS ticket number if applicable, e.g. 'ODS-4484'. Null for non-ticket work."
  sprint_id: "Sprint ID (end date string, e.g. '2026-03-03') to assign to. Null for backlog/personal."
  commitment_level: "Work tasks only: 'sprint_committed', 'sprint_stretch', or 'backlog'"
  jn_bucket: "Work tasks only. Timecard category: 'planning', 'development', 'sustaining', 'overhead', 'training'"
  tier: "Personal tasks only: 1 (hard deadline/external), 2 (important, no external accountability), 3 (someday/maybe)"
  status: "Initial status. Defaults to 'not_started'."
  estimate_hours: "Optional time estimate in hours"
  deadline: "Hard deadline date if one exists (ISO format). Distinct from sprint end date."
  parent_task_id: "ID of parent task for subtasks. One level of nesting only."
  is_commitment: "True when Matthew has made an explicit promise to someone (colleague, himself with deadline)"
  commitment_notes: "Context for commitments: who, when, what was promised"
  priority_rank: "Relative ordering. Scoped to commitment_level (work) or tier (personal). Rank 1 = highest within that scope."
  pinned: "Personal Tier 3 only. Pinned items appear in the 'what this is all for' motivational section of the tracker."
  private: "Personal tasks only. Private tasks are invisible to goal-bot and to the shared task surface — use for anything that shouldn't surface outside this tracker (e.g. gifts, surprises)."
  notes: "Detailed context, history, or background. Not shown in list views."
```

**`create_tasks`**
```
description: "Batch create multiple tasks at once. Use when Matthew drops several items at once — brain dumps, sprint planning intake, or listing out personal errands. More efficient than multiple create_task calls."
params:
  tasks: "List of task objects. Each follows the same schema as create_task."
```

**`get_task_detail`**
```
description: "Get full detail for a single task including rich notes, history, and actual_hours (computed from time entries, work tasks only). Children are returned inline with full detail. Use when Matthew says he's going to work on a specific task and needs context, or when reviewing a task's history."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
```

**`update_task`**
```
description: "Update one or more fields on a single task. Use for field changes like reprioritizing, updating notes, changing status, setting deadlines, or adding blocked_reason. For completing a task, prefer complete_task. For dropping a task, prefer nuke_task. For updating many tasks at once, use batch_update_tasks."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
  (all task fields): "Any field(s) to update. Only provided fields are changed."
```

**`batch_update_tasks`**
```
description: "Update multiple tasks in a single call. Use for EOD status sweeps (marking several tasks done/in_progress), sprint reassignments (moving tasks between sprints), tier reorganizations, or any situation where 3+ tasks change at once."
params:
  updates: "List of {id, type, ...fields} objects. Each follows the same field schema as update_task."
```

**`complete_task`**
```
description: "Mark a task as done. Sets status='done' and completed_at=now. Use when Matthew says a task is finished, done, completed, shipped, merged, or resolved. This is the default for any positive completion — prefer this over update_task(status='done')."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
```

**`nuke_task`**
```
description: "Mark a task as explicitly dropped — decided not to do. Sets status='nuked', preserves all data. Use when Matthew decides to abandon, drop, skip, or deprioritize indefinitely. Default choice when removing a task — only use delete_task if the task was a mistake or duplicate that shouldn't appear in any history."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
```

**`delete_task`**
```
description: "Soft delete a task (sets deleted_at). Filtered out of ALL queries including sprint reviews. Use ONLY for confirmed mistakes or duplicates — tasks that should never have existed. For tasks Matthew chose not to do, use nuke_task instead (preserves visibility in sprint history)."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
```

**`restore_task`**
```
description: "Restore (undelete) a soft-deleted task by clearing its deleted_at. The reverse of delete_task — use when a task was deleted by mistake. Acts only if the task is currently soft-deleted; if it isn't deleted this is a no-op and simply returns the current record. Returns null if no task with that ID exists."
params:
  id: "Task ID"
  type: "Task type: 'work' or 'personal'"
```

### Task Queries

**`get_open_tasks`**
```
description: "Get all open (non-done, non-nuked, non-deleted) tasks. Returns lightweight fields without rich notes. Use for ad-hoc queries like 'what personal items have I been carrying?' or 'show me all blocked work tasks.' For daily tracker generation, prefer get_tracker_data which includes computed annotations. Use min_days_open=7 with type='personal' for weekly personal item review (Mondays). Use min_days_open=30 for monthly stale item review."
params:
  type: "Filter by type: 'work', 'personal', or 'all'. Default 'all'."
  min_days_open: "Only return tasks with days_carried >= this value. Useful for stale item reviews."
```

**`get_sprint_tasks`**
```
description: "Get all tasks for a sprint including done, nuked, waiting, and delegated — complete sprint picture. Excludes soft-deleted. Use for mid-sprint progress checks, sprint retros, and completion rate analysis. For daily tracking, get_tracker_data already includes active sprint data."
params:
  sprint_id: "Sprint ID (end date string). Defaults to active sprint."
```

**`get_tasks_updated_on`**
```
description: "Get tasks that had status changes, time logged, or notes updated on a specific date. Returns flat list. Use as optional cross-check when generating standup summaries — catches tasks touched but not discussed in conversation."
params:
  date: "Date to check (ISO format)"
```

**`search_tasks`**
```
description: "Keyword-search tasks by title and notes. Returns lightweight ranked candidates (id, title, tier, status, type) — title matches rank above notes-only matches. This is a cheap keyword search, not semantic: it surfaces candidates for you to reason over, and will miss zero-token-overlap synonyms (e.g. 'bronco' won't match 'vehicle registration'). For those, search a synonym or fall back to get_open_tasks. Searches open work and personal tasks by default; set include_done/include_deleted to widen to completed or soft-deleted history."
params:
  query: "Keyword or phrase to match against title and notes."
  include_done: "Include tasks with status 'done'. Default False."
  include_deleted: "Include soft-deleted tasks. Default False."
  limit: "Maximum number of results to return. Default 20."
```

**`get_estimation_accuracy`**
```
description: "Compare estimated vs actual hours for completed work tasks. Returns per-task rows (title, estimate_hours, actual_hours, ratio where ratio = actual/estimate) plus the aggregate median ratio. A ratio > 1 means the task took longer than estimated. Only work tasks carry estimates and time entries, so personal tasks are never included. Use for the periodic estimation-accuracy review."
params:
  n: "Optional cap to the most-recent N completed tasks."
  type: "Optional task type filter ('work' or 'personal'). Only work tasks have estimation data, so 'personal' returns no rows."
```

### Composite Queries

**`get_tracker_data`**
```
description: "Single call returning everything needed for daily tracker generation and morning kickoff. Returns: open work tasks with computed annotations (is_stale, is_blocked, has_upcoming_deadline), open personal tasks with same annotations, active sprint info + all sprint tasks, today's daily log (whoop data, previous observations), and tier3_review_due flag. This is always the first call in a new day's session."
```

### Time Tracking

**`log_time`**
```
description: "Log a time entry for a work task. Call when a time block in the tracker artifact is completed. Time blocks in the artifact are ephemeral planning; time_entries in the DB are the permanent record for timecards. JN bucket on the entry may differ from the task's default bucket."
params:
  work_task_id: "ID of the work task"
  date: "Date the work was done (ISO format)"
  duration_minutes: "Duration in minutes"
  jn_bucket: "Timecard category: 'planning', 'development', 'sustaining', 'overhead', 'training'. PR reviews default to 'development' unless the PR is for a bug/maintenance (then 'sustaining')."
  notes: "Optional. What happened during this block."
```

**`delete_time_entry`**
```
description: "Hard-delete a time entry by its ID and return the removed row (date, bucket, minutes, work_task_id, notes) so the removal can be confirmed. Use to remove a mis-logged entry — e.g. time logged against the wrong task or in the wrong chat. Unlike tasks, a wrong time entry has no analytic value, so this is a permanent delete, not a soft delete. Returns null if no entry with that ID exists."
params:
  time_entry_id: "ID of the time entry to delete"
```

**`get_timecard`**
```
description: "Get aggregated time data for timecard generation. Groups by date + jn_bucket, includes ODS ticket references. Use when Matthew asks for a timecard — pair with get_time_gaps to identify incomplete days."
params:
  start_date: "Start of range (ISO format)"
  end_date: "End of range (ISO format)"
```

**`get_time_gaps`**
```
description: "Compare logged time per day against ~8h expected. Flags days with incomplete logging. Use alongside get_timecard to identify where conversation context is needed to fill gaps, and to generate uncertainty notes in the timecard."
params:
  start_date: "Start of range (ISO format)"
  end_date: "End of range (ISO format)"
```

### Daily Logs

**`log_daily`**
```
description: "Create or update a daily log entry. Use to record Whoop data when Matthew shares recovery scores, and for general day context notes. Creates the entry if it doesn't exist, updates if it does."
params:
  date: "Date (ISO format)"
  whoop_recovery: "Recovery percentage (0-100)"
  whoop_hrv: "Heart rate variability"
  whoop_sleep_hours: "Hours of sleep"
  whoop_rhr: "Resting heart rate"
  notes: "General day context"
```

**`log_reflection`**
```
description: "Set or update the structured EOD reflection for a date. All fields optional for partial updates. Matthew's answers go in the four reflection fields. Claude's pattern observations (streaks, correlations, trajectory notes) go in the observations field — kept separate from Matthew's self-assessment."
params:
  date: "Date (ISO format)"
  moved_forward: "What moved forward today — completions, partial progress, decisions, agency moments. Matthew's input."
  didnt_move: "What didn't move and why — blockers vs. choices. Matthew's input."
  do_differently: "What would I do differently — learning extraction. Matthew's input."
  protect_tomorrow: "One thing to protect tomorrow — implementation intention. Matthew's input."
  observations: "Claude's pattern observations — momentum streaks, whoop correlations, trajectory notes. Claude writes this, not Matthew."
```

**`get_daily_log`**
```
description: "Get a single day's log including whoop data, reflections, and observations. Use when reviewing a specific day's data."
params:
  date: "Date (ISO format)"
```

**`get_daily_logs`**
```
description: "Get daily logs across a date range. Use for pattern analysis — whoop-to-output correlation, distraction windows, estimation accuracy, reactive vs. proactive balance over time."
params:
  start_date: "Start of range (ISO format)"
  end_date: "End of range (ISO format)"
```

### Sprint Management

**`set_active_sprint`**
```
description: "Create a new sprint and/or mark it as active, deactivating the previous sprint. Use at sprint boundaries (Tuesday EOD or Wednesday morning) to transition between sprints."
params:
  sprint_id: "Sprint ID — use the end date as ID, e.g. '2026-03-17'"
  start_date: "Sprint start date (ISO format). Required when creating a new sprint."
  end_date: "Sprint end date (ISO format). Required when creating a new sprint."
```

### System Meta

**`set_meta`**
```
description: "Write a system-level metadata value. Currently used for: 'last_tier3_review' (date string) — set after completing a quarterly Tier 3 reflection so get_tracker_data can compute tier3_review_due. Read is handled server-side, not via a separate tool."
params:
  key: "Metadata key, e.g. 'last_tier3_review'"
  value: "Value as text string"
```

### Date / Time

**`get_time`**
```
description: "Get the current date and time. Use at the start of any session to orient on today's date, day of week, and timezone. Essential for date-sensitive operations like sprint boundaries, deadlines, and daily log entries."
params:
  timezone: "Optional IANA timezone string (e.g. America/New_York, UTC). Defaults to America/Los_Angeles (PT) when omitted."
```

## Status Definitions

### Work Task Statuses
| Status | Meaning |
|--------|---------|
| not_started | In backlog or sprint, no work done |
| in_progress | Actively being worked on |
| in_review | PR submitted, awaiting review |
| blocked | Can't proceed — blocked_reason set |
| waiting | Externally dependent, nothing to do (e.g. "awaiting PR review", "waiting on customer response"). Distinct from blocked. blocked_reason set. |
| done | Completed and verified |
| delegated | Handed off to someone else |
| nuked | Explicitly decided not to do. Data preserved. |

### Personal Task Statuses
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
- **Completed and nuked sprint items** are included in the artifact for sprint-in-progress visibility and transparency
- **Time blocks** are planned and tracked in the artifact only — they're ephemeral (current day only) and feed `log_time()` calls but are not stored in the DB
- **Pinned Tier 3 items** appear in a "what this is all for" section — motivational, not a to-do list. Matthew controls which items are pinned via `update_task()`.

## Migration Plan

1. Build MCP server with core CRUD + query tools
2. Seed DB from most recent tracker (one-time script)
3. Run in parallel for ~1 week: MCP is source of truth, artifact is view layer. Validate nothing is lost.
4. Iterate on tool ergonomics based on actual usage
5. Port to VPS once stable

## Not In Scope (for now)
- Habit tracking (guitar practice streaks, etc.)
- Whoop API integration (door is open via daily_logs schema)
- Notification system
- Semantic / embedding-based search (keyword `search_tasks` ships now; FTS5 and beyond tracked in TODO.md)
- Docker containerization (future: for VPS deployment)
- CI/CD pipeline (future: for VPS deployment)
- Port to VPS with managed backups
- Integration with transcript summarizer
- Integration with Jira (potential bidirectional sync with ODS tickets)

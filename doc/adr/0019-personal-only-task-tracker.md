# ADR-0019: Task-tracker is personal-only — work tracking leaves the system

**Status:** Accepted

## Context
Task-tracker began life on Matthew's work laptop tracking both halves of the day: work tasks (sprints, ODS tickets, JN-bucket time entries for timecards) and personal tasks. The work half has since moved to a separate work assistant maintained outside this repo. When the tracker migrated to prod Postgres (ADR-0008), only `personal_tasks` and `daily_logs` were ever populated — `work_tasks`, `time_entries`, and `sprints` were created by migration 0003 but left empty, with the full work history deliberately retained in the legacy standalone repo's SQLite (`~/dev/task-tracker-mcp`, kept as backup). Prod holds zero rows in all three tables, and no `goal_version` carries a `task_ref_source = 'work'` reference (verified 2026-08-13). The code, tool surface, and schema still carried the whole dual-track model.

## Decision
Task-tracker is a **personal** tracker. Everything work-only is removed:

- **Tools removed:** `log_time`, `delete_time_entry`, `get_timecard`, `get_time_gaps`, `set_active_sprint`, `get_sprint_tasks`, `get_estimation_accuracy` (estimates and time entries only ever existed on work tasks).
- **Tool surface simplified:** the `type: 'work' | 'personal'` discriminator disappears from every remaining task tool; work-only fields (`ods_ticket`, `sprint_id`, `commitment_level`, `jn_bucket`, `estimate_hours`) go with it. `get_open_tasks` and `get_tasks_updated_on` return flat lists instead of per-type dicts; `get_tracker_data` drops its `work` and `sprint` sections.
- **Domain/infrastructure removed:** `WorkTaskEntity`, `TimeEntryEntity`, `SprintEntity` and their enums, factories, ports, use cases, and adapters (Postgres and SQLite twins).
- **Schema:** migration 0007 drops `tasktracker.work_tasks`, `tasktracker.time_entries`, `tasktracker.sprints`, and narrows `goal_version.task_ref_source` to `('personal')`. Zero rows are lost (all three tables empty in prod and dev).
- **Cross-package port:** `TaskQueryClient.get_task_status` accepts only `source='personal'`; goal-bot's `TaskRefSource` enum loses `WORK`. Amends ADR-0005: one-off goals may reference **personal** tasks only (work goals were already excluded there; now work *refs* are impossible too).
- **The legacy SQLite** (`~/dev/task-tracker-mcp/.db/tasks.db`: 138 work tasks, 173 time entries, 7 sprints) is the archival record of the work half and is not touched by this change.

## Consequences
- The shared surface (ADR-0018) is unchanged in tool names; its read tools now speak personal-only shapes.
- The friction ratchet is honored in the right direction: fewer tools, fewer parameters, no new structure.
- If work tracking ever returns to this codebase, it re-enters by a new ADR and new migrations — not by resurrecting these tables.
- `daily_logs` (Whoop + EOD reflection) and `system_meta` are personal and stay.

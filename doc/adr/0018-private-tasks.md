# ADR-0018: Private personal tasks are invisible outside the personal tracker; sharing is decided by which server a bot mounts

**Status:** Accepted

## Context
Goal-bot runs in a group-chat setting: personal tasks it ingests as goal candidates can surface publicly. Some open tasks must not (e.g. a surprise gift for a partner). Goal-bot reaches task data only through the published `TaskQueryClient` port (ADR-0007), so a data-layer gate is possible in one place. Separately, future shared bots may want direct task-tracker MCP tools; client-side tool allowlists filter tool *names*, not *rows*, and prompt-level instructions are not enforcement.

## Decision
- `personal_tasks.private` boolean, default false, settable via `create_task`/`update_task` (optional flag — no new required fields, per the friction ratchet). `work_tasks` carry no flag (never goal candidates, ADR-0005).
- **Port gate:** `get_personal_candidates` never returns private tasks. `get_task_status` answers **None** for a private task — deliberately indistinguishable from nonexistent. None is a **no-signal** answer: callers must treat it as "say nothing", never as evidence the task completed or was dropped (the NULL-TOLERANCE posture applied to refs).
- **New refs blocked:** goal-version creation validates `task_ref` through the port; refs to private / foreign / missing tasks are rejected identically at write time. A dark ref can therefore only arise by deliberately privatizing an already-referenced task — the goal keeps working, it just loses status sync.
- **Prospective only:** flipping `private` retracts nothing already ingested into the goalbot schema. Mark the task private *before* any goal-setting conversation touches it.
- **Shared MCP surface:** `create_shared_app()` (run via `python -m task_tracker --shared`) exposes a curated read-only tool grant (`get_task_detail`, `get_open_tasks`, `search_tasks`, `get_tasks_updated_on`) backed by a repository variant that adds `private = false` to every personal-task read at the SQL layer, including child-task loads.
- **Deployment rule:** privacy is enforced by *which server a bot's config mounts* — full server for the personal tracker bot, shared server (or goal-bot's own MCP, which only sees the port) for anything other people can talk to. Never by client config, argument defaults, or prompts: any bot reachable by others is untrusted with respect to private rows.

## Consequences
- One bit, three gated doors (query-client port, shared MCP surface, ref validation); the full personal tracker sees everything, unchanged.
- Goal-bot planning code must honor the no-signal contract on `get_task_status` (documented on the port).
- The toy seed creates its own backing errand tasks — refs must now resolve at creation time.
- Spec edits: `private` column + tool params in task-tracker `docs/spec.md`; shared-surface grant documented there.

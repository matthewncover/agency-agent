# TODO / Deferred Work

Tracked follow-ups that are intentionally out of the current build. See
`docs/spec.md` for the authoritative tool/schema definitions.

## Graduate `search_tasks` from LIKE to FTS5

`search_tasks` currently uses a plain `LIKE %query%` scan over `title` + `notes`
(see `SqliteTaskRepositoryAdapter.search_tasks`). At ~40 open tasks this is
indistinguishable in latency from a real index and trivially correct.

Graduate to SQLite **FTS5** when the done/deleted history grows large enough that
the linear scan or the lack of relevance ranking starts to matter:

- FTS5 external-content (or contentless) virtual table over `title` + `notes`.
- `INSERT`/`UPDATE`/`DELETE` triggers on `work_tasks` and `personal_tasks` to keep
  the index synced.
- Swap the adapter query to `MATCH` + `bm25()` ranking; the tool/use-case/port
  signatures stay the same, so this is an infrastructure-only change.

Known limit FTS5 does **not** fix: zero-token-overlap misses (e.g. "bronco" vs
"Vehicle registration transfer"). Handle at call time (synonyms / fall back to
`get_open_tasks`), not in the index.

## `task_history` audit table

Status changes over time, for pattern analysis (days-carried, avoidance windows).
Currently inferred from conversation.

- New `task_history` table: `task_id`, `type`, `field`, `old`, `new`, `changed_at`.
- Write hooks on **every** mutation path (the reason this is deferred — it's the
  one change that isn't localized).

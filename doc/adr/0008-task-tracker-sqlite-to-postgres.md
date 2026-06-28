# ADR-0008: Migrate task-tracker from SQLite to Postgres
 
**Status:** Accepted
 
## Context
meta-plan §2 / ADR-0003 record "separate schemas on one Postgres instance." The live task-tracker schema is **SQLite** (no schemas; `AUTOINCREMENT`/`DATETIME`/`REAL`), so the prior decision wasn't satisfiable as-is. A v0.1 draft recommended staying on SQLite and integrating via interface. Matthew chose to migrate; task-tracker is **clean-architecture** (ADR-0009), so the DB is an adapter detail.
 
## Decision
**Migrate task-tracker SQLite → Postgres.** Implementation = write Postgres repository adapters; domain + use-case layers untouched. Data path: ~100 rows, CSV dump/load is acceptable. This **confirms ADR-0003** (not superseded) and unblocks the profile schema (ADR-0004).
 
## Consequences
- ADR-0003 stands; "one Postgres instance" becomes literally true.
- Enables `profile.person` FK links from task-tracker (impossible under SQLite).
- Migration scope includes person-stamping (ADR-0004) and the `daily_logs` PK change to `(owner_id, date)` (architecture §7 OQ-D).
- Cost is bounded precisely because of clean architecture — the migration is the concrete payoff of ADR-0009.
- task-tracker's MCP queries repoint to the Postgres adapter; external behavior unchanged.

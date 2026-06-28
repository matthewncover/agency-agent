# ADR-0007: Cross-package access via published ports (Person port + typed task client); no raw cross-schema SQL
 
**Status:** Accepted
 
## Context
With both packages on Postgres (ADR-0008), cross-schema SQL is physically possible. It remains undesirable: it couples a package to another's internal tables and bypasses its ports, violating clean architecture (ADR-0009). goal-bot needs `profile.person`, task candidates, referenced-task status, and `daily_logs` Whoop/sleep signal.
 
## Decision
- **`profile.person`:** accessed through the `profile` package's published `Person` repository port; both packages depend on `profile`'s public API, not its tables.
- **task data (goal-bot → task-tracker):** through task-tracker's **typed, read-only client** (a published port) — candidate-gathering, referenced-task status, `daily_logs.whoop_recovery/sleep` (Matthew only). **Not MCP transport** (unreliable for deterministic sync). **Not raw cross-schema SQL** (clean-arch boundary).
- **LLM-facing:** candidate-gathering done by goal-bot via the typed client, surfaced to the LLM as a prepared list; the LLM never holds task-tracker's MCP.
- Read-only for MVP; any future write (completion sync) is a separate, explicit port + ADR.
## Consequences
- Deterministic ops don't depend on LLM behavior or MCP reliability.
- Candidate selection stays deterministic; LLM cannot issue arbitrary task writes.
- task-tracker exposes a public typed client alongside its MCP (additive; standalone use unaffected).
- Preserves the acyclic DAG.

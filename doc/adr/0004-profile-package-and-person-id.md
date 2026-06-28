# ADR-0004: Identity + Tier-1 authored profile live in a `profile` package; person_id is caller-supplied
 
**Status:** Accepted — Superseded by ADR-0012
 
## Context
agency-agent serves multiple individuals across capabilities (task-tracker, goal-bot) that each learn about the user. Identity and the authored "who this person is" profile are the natural shared primitives. A `shared` name was rejected as a junk-drawer; `profile` names what it owns. Multi-user is ~2 months out (not hypothetical), so the seam should exist now.
 
## Decision
- A **`profile`** package/schema owns `person` and the **Tier-1 authored profile** (human-owned ground truth).
- task-tracker and goal-bot link rows to `profile.person` via `owner_id`.
- `profile.person` is **channel-agnostic**; `telegram_user_id → person_id` lives in the **agent** layer.
- **`person_id` is a caller-supplied parameter on every task/goal client + MCP call from day one** — no global "current person." Single-user MVP passes the one id; multi-user needs no retrofit. Always-filter-by-owner enforcement lands with the second user.
- **Standalone task-tracker = `profile` + `task-tracker`.**
## Consequences
- Reverses v0.1 (person-in-goal-bot); refines v0.2 (`shared` → `profile`).
- Tier-2/3 memory stays domain-local (ADR-0011 boundary); only human-approved cross-domain insight reaches `profile`.
- Standalone unit is `profile + task-tracker`; `profile` carries no goal logic.
- DAG: profile depends on nothing; task-tracker/goal-bot/agent → profile. Acyclic.

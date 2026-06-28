# ADR-0011: Observations stay domain-local; only human-approved cross-domain insight reaches `profile`
 
**Status:** Accepted
 
## Context
The system produces observations in two places (task context in task-tracker; goal "what shifted"/friction in goal-bot) and wants, eventually, cross-bot knowledge about the individual. The three-tier trust boundary (Tier-1 authored/human-owned) must survive.
 
## Decision
- **Task observations** live in **task-tracker** (existing `daily_logs.observations`/Whoop/EOD fields, ported as-is).
- **Goal observations + goal insights** (Tier-2 events, Tier-3 digest) live in **goal-bot**.
- **Tier-1 authored profile** lives in **`profile`** — the only memory both capabilities treat as ground truth.
- **Cross-domain synthesis is FUTURE and human-gated:** the agent may mine both streams and *propose* hypotheses about the individual; approved items graduate into Tier-1 via `profile`'s port. Delivered as an **on-demand MCP tool the human calls** (compare profile vs. logs), on a periodic (~10-week) cadence — never an automatic background writer. Parked in `doc/future-ideas.md`; not built for MVP.
## Consequences
- No silent rewrites of the authored profile; the trust boundary holds.
- Observations are read where they're produced; no premature centralization.
- The only anticipated cross-package write (Tier-3→Tier-1 graduation) is explicit, ported, and human-approved.

# ADR-0010: Agent runtime, domain capabilities, and composition root are separated
 
**Status:** Accepted — Superseded by ADR-0014
 
## Context
The system needs a runtime that can take on a persona/capability (schedule, build context, run an LLM turn, deliver, persist) without being welded to a specific domain. goal-bot is the first capability; a multi-user task-tracker capability follows in ~2 months. Clean architecture (ADR-0009) requires concrete wiring to live in exactly one sanctioned place.
 
## Decision
- **`agent` (runtime):** owns the generic loop and orchestration. Depends on **capability ports** and `profile`. Knows ports, not concrete capabilities. Could run standalone.
- **Capabilities (`goal-bot`, later `task-tracker`):** implement capability ports; own their domain logic and domain-specific observations/memory.
- **`app` (composition root):** the single place permitted to know concretes — instantiates adapters (Telegram, goal capability, task client, Postgres) and binds them to agent's ports. The process entrypoint.
- Persona/context is capability-scoped at runtime; the agent can also (future) mine across capabilities to propose profile updates (ADR-0011 boundary; human-gated).
## Consequences
- agent imports no concrete capability → standalone-capable, testable against fake ports.
- Adding a capability = implement the port + register it in `app`; no agent change.
- The composition root is the only rule-breaker, as clean architecture intends.
- Ritual split: generic loop in agent; goal-specific selection (smart-subset, need/want, carry-over, lighter-day nudge) in goal-bot. Spec §3 to be split accordingly.

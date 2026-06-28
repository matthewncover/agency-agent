# ADR-0006: Five packages (`profile`, `task-tracker`, `goal-bot`, `agent`, `app`)
 
**Status:** Accepted — Superseded by ADR-0014
 
## Context
v0.2 used three packages and folded the bot into goal-bot. Two changes invalidate that: (1) the runtime gets a second consumer (multi-user, agent-driven task-tracker) in ~2 months, so extracting the runtime now beats retrofitting; (2) clean architecture (ADR-0009) wants the composition root isolated.
 
## Decision
- **MVP = five packages:**
  - `profile` — person + Tier-1 authored profile. deps: none.
  - `task-tracker` — tasks (personal + work) + task observations + own MCP. deps: profile.
  - `goal-bot` — goal domain + goal MCP + Tier-2/3 goal memory. deps: profile, task-tracker.
  - `agent` — domain-agnostic runtime (scheduler, Telegram, LLM loop); depends on capability **ports** + profile; imports no concrete capability.
  - `app` — composition root; the only place that names concrete adapters and wires them into agent's ports; the process entrypoint. deps: agent, goal-bot, task-tracker, profile.
- Keep the capability port minimal (one capability, goals) for MVP; no plugin framework until task-tracker actually plugs in.
## Consequences
- Reverses v0.2 "bot folded into goal-bot."
- `agent` is genuinely standalone-capable (depends on ports, not capabilities).
- Standalone deploy = profile + task-tracker.
- meta-plan §3 layout updated to five packages; `shared` → `profile`; no separate `bot`.
- See ADR-0010 for the agent/domain/composition-root split rationale.

# ADR-0014: Defer the standalone `agent`/`app` package split; MVP = three packages
 
**Status:** Accepted
 
**Supersedes:** ADR-0010 (agent/runtime/composition split as separate packages) and ADR-0006 (five-package decomposition); re-states their still-valid core below.
 
## Context
ADR-0006 specced five packages and ADR-0010 split out a domain-agnostic `agent` runtime and an `app` composition root as **separate packages**, justified by a second capability (multi-user, agent-driven task-tracker) ~2 months out: extract the runtime now to avoid a retrofit. On review, that justification mostly collapses against ADR-0009: clean architecture is precisely what makes extracting a clean runtime from a monorepo later a **lift-out, not a rewrite**. The same property that makes the Postgres migration (ADR-0008) a cheap adapter swap makes the agent extraction cheap when the second consumer actually exists. So the separate-package seam earns nothing now and is idle abstraction if the 2-month horizon slips. The goal is to **get to coding soon**.
 
## Decision
**Re-stated from 0006/0010 (still in force):**
- One monorepo, package boundaries (ADR-0002).
- The runtime is the **`agent`** *concern* (scheduler + Telegram + LLM loop), domain-agnostic; goal-specific logic (smart-subset, need/want, carry-over, lighter-day nudge) is the goal capability.
- Clean architecture / ports-and-adapters everywhere (ADR-0009); cross-package access via published ports (ADR-0007).
- Standalone deploy = `profile` + `task-tracker`.
**New (the deferral):**
- **MVP = three packages:** `profile`, `task-tracker`, `goal-bot`. The `agent`-runtime loop and the composition entrypoint live **inside goal-bot as internal modules**, behind a strict in-code module boundary, **not** as separate `agent`/`app` package directories.
- The discipline that replaces the package seam: **agent-generic logic and goal-specific logic must not bleed together in the same module.** Keeping that line visible is what preserves the cheap lift-out.
- **Revisit** the extraction if/when the second capability (multi-user task-tracker as an agent-driven capability) actually lands.
## Consequences
- Reverses 0010's separate-package split and 0006's package *count* (five → three); their original text is preserved unchanged per the append-only rule, status lines point here.
- **Bet made explicit:** we trade the (cheap, clean-arch-backed) future extraction cost for a simpler MVP now. If the runtime-extraction turns out painful later, that is the cost of this decision — accepted because clean architecture makes it unlikely.
- ADR-0007's inter-package port rules still hold for `profile`/`task-tracker`/`goal-bot`. The agent↔capability port from 0010 becomes an **internal seam** inside goal-bot rather than a cross-package port.
- meta-plan §2/§3 updated to three packages; spec §3's morning-ritual split is described as a generic-vs-goal-specific *module* line rather than a package boundary.
- No plugin framework (0006's caveat) — unchanged; even more clearly unwarranted at three packages.

# ADR-0009: Clean architecture (ports & adapters) is a system-wide convention
 
**Status:** Accepted
 
## Context
task-tracker is already written in clean architecture, which is what makes the Postgres migration (ADR-0008) an adapter swap rather than a refactor, and what makes the published-port access model (ADR-0007) natural. To keep that property across the system, it should be an explicit convention, not an accident of one package.
 
## Decision
- **All agency-agent packages follow clean / ports-and-adapters architecture.** Domain and use-case layers depend on abstractions (ports); frameworks, transports (MCP/Telegram), and databases (Postgres) are adapters at the edge.
- Cross-package access goes through **published ports** (ADR-0007), never another package's internal tables or framework objects.
- Persistence is swappable behind repository ports (the property ADR-0008 relies on).
## Consequences
- New goal-bot, agent, and profile code must layer domain/use-case vs. adapters from the start.
- DB engine, MCP transport, and Telegram are replaceable without touching domain logic.
- Guardrail: a future "just query the other schema directly" shortcut violates this ADR and must instead add a port.
- Slightly more upfront structure in goal-bot; pays for itself in testability and the migration/integration cheapness already demonstrated.

# ADR Index

ADRs are canonical for their decision. behavior-spec.md is canonical for behavior until the behavioral ADRs land.

The entry point for decisions: read this to find the right ADR, never the raw directory listing. Updated in the same commit as any new or superseded ADR. Every field below is derived from each ADR's own status / supersession lines.

| Number | Title | Status | Supersedes | Superseded by |
|---|---|---|---|---|
| [0004](0004-profile-package-and-person-id.md) | Identity + Tier-1 authored profile live in a `profile` package; person_id is caller-supplied | Accepted — Superseded by ADR-0012 | — | [ADR-0012](0012-group-profile-supertype.md) |
| [0005](0005-goals-reference-tasks.md) | One-off goals reference tasks (goal → task); concepts stay distinct | Accepted | — | — |
| [0006](0006-five-packages.md) | Five packages (`profile`, `task-tracker`, `goal-bot`, `agent`, `app`) | Accepted — Superseded by ADR-0014 | — | [ADR-0014](0014-three-package-mvp.md) |
| [0007](0007-cross-package-ports.md) | Cross-package access via published ports (Person port + typed task client); no raw cross-schema SQL | Accepted | — | — |
| [0008](0008-task-tracker-sqlite-to-postgres.md) | Migrate task-tracker from SQLite to Postgres | Accepted | — | — |
| [0009](0009-clean-architecture-convention.md) | Clean architecture (ports & adapters) is a system-wide convention | Accepted | — | — |
| [0010](0010-agent-runtime-composition-split.md) | Agent runtime, domain capabilities, and composition root are separated | Accepted — Superseded by ADR-0014 | — | [ADR-0014](0014-three-package-mvp.md) |
| [0011](0011-domain-local-observations.md) | Observations stay domain-local; only human-approved cross-domain insight reaches `profile` | Accepted | — | — |
| [0012](0012-group-profile-supertype.md) | Group/household profile owns shared goals via a `profile` supertype | Accepted | [ADR-0004](0004-profile-package-and-person-id.md) | — |
| [0013](0013-chapter-scoped-goals.md) | Goals are chapter-scoped; cross-chapter lineage deferred | Accepted | — | — |
| [0014](0014-three-package-mvp.md) | Defer the standalone `agent`/`app` package split; MVP = three packages | Accepted | [ADR-0010](0010-agent-runtime-composition-split.md), [ADR-0006](0006-five-packages.md) | — |
| [0015](0015-language-python.md) | Implementation language is Python (the "TypeScript monorepo" assumption was never a decision) | Accepted | — (creates a decision where only an assumption existed) | — |
| [0016](0016-rotation-groups.md) | Rotation groups — cadence is scheduled across member goals, not inside one | Accepted | — | — |
| [0017](0017-liveness-heartbeat.md) | Liveness heartbeat — an external dead-man's switch watches the system's promise to show up | Accepted | — | — |
| [0018](0018-private-tasks.md) | Private personal tasks are invisible outside the personal tracker; sharing is decided by which server a bot mounts | Accepted | — | — |

> ADRs 0001–0003 are referenced in project history (see the prior combined-bundle index and `doc/process/meta-plan.md`) but were not part of the split bundle; no per-file ADR bodies exist for them yet.

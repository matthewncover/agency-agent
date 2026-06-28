# ADR-0015: Implementation language is Python (the "TypeScript monorepo" assumption was never a decision)
 
**Status:** Accepted
 
**Supersedes:** nothing — there is no prior language ADR. This record *creates* a decision where only an unexamined assumption existed.
 
## Context
 
Every doc through v0.5 describes agency-agent as a "TypeScript monorepo." That phrase was never the output of a decision. A grep across `architecture.md`, `meta-plan.md`, and the ADR set finds the *language* argued nowhere, while far cheaper-to-reverse choices each got a full record: five-vs-three packages (0006/0014), the agent/app seam (0010/0014), clean-arch as convention (0009), the Postgres adapter swap (0008), enum representation, package naming. The most expensive-to-reverse decision in the project — the language the whole thing is written in — rode along as a label and was never litigated. That asymmetry is the tell: TypeScript was defaulted, not chosen.
 
Two facts, surfaced late, collapse the question:
 
1. **The only package that already exists is Python.** `task-tracker` is written in Python, in clean architecture (ADR-0009), on FastMCP. The single concrete artifact under the "TypeScript monorepo" label contradicts the label.
2. **The migration tooling chosen for the Postgres work is Alembic** — SQLAlchemy/Python. Driving schema for a Node app with a Python toolchain would mean two runtimes and schema types defined in Python but consumed in TS, forfeiting the end-to-end-types property that is TypeScript's main reason to exist here. Reaching for Alembic *is* the project's center of gravity already being Python.
On the merits for this system — an LLM agent loop + Telegram + an MCP server + Postgres — Python is at least as strong as TypeScript and plausibly stronger: `python-telegram-bot` is mature, the Anthropic SDK and the official MCP SDK (FastMCP) are first-class, SQLAlchemy + Alembic is best-in-class for the migration story, and the maintainer (a sole maintainer of a personal tool) is more fluent in it — a load-bearing technical fact for long-run maintainability, not a soft preference. TypeScript's distinctive payoff — end-to-end static types and one language shared with a web frontend — does not apply: there is no frontend (the surface is Telegram), and the expensive boundaries are enforced structurally (clean-arch ports; the DB constraints in migrations 0001/0002) rather than by the type system. The clean-architecture discipline the ADRs depend on is language-agnostic and ports to Python directly.
 
The cost normally feared in a language switch — porting an existing TypeScript codebase — is **zero**: no TypeScript exists. The project is pre-coding; this is the cheapest possible moment to set the language, and the decision resolves *toward* the language the existing package and the chosen tooling already use.
 
## Decision
 
- **The implementation language is Python.** The "TypeScript monorepo" framing is withdrawn wherever it appears in the docs (meta-plan, architecture, spec) and replaced with a Python monorepo framing.
- **Migrations: Alembic** (SQLAlchemy), as a **single linear history at the repo root** (`migrations/`) managing **both schemas** (`profile`, `goalbot`) on the one Postgres instance (ADR-0003). The hand-authored DDL for 0001 (profile schema) and 0002 (goal-bot schema) is **hosted inside the Alembic revision modules** — `upgrade()` runs the DDL verbatim via `op.execute()`, `downgrade()` does `DROP SCHEMA … CASCADE` — rather than kept as separate `.sql` files driven by a dbmate-style `migrate:up/down` runner. The DDL is **not** re-expressed as `op.create_table()` Python, so CHECK constraints, partial unique indexes, composite / cross-schema FKs, and `GENERATED ALWAYS AS IDENTITY` columns survive exactly. task-tracker's Postgres DDL (ADR-0008) joins the same linear tree as a later revision.
- **MCP: FastMCP**, consistent with the existing `task-tracker` package.
- **Nothing structural changes.** ADRs 0002/0007/0009/0014 (monorepo, ports, clean architecture, three packages) are language-agnostic and stand unchanged. The package *vocabulary* in the meta-plan shifts from npm-workspace framing to a Python monorepo layout — **a uv workspace with one `src`-layout package per member, mirroring the existing `task-tracker`**; this is cosmetic against the architecture and is doc-reconciliation work, not a decision.
## Consequences
 
- A decision record now exists for the language; a future reader sees Python was chosen deliberately against the prior TypeScript assumption, with the reasoning, rather than finding the choice unexplained.
- `task-tracker` needs no language port — it is already Python/clean-arch/FastMCP. The remaining task-tracker work is the SQLite→Postgres adapter swap (ADR-0008), unaffected by this ADR.
- The DDL is unaffected in substance: the hand-authored SQL is hosted verbatim inside the Alembic revisions (not re-expressed in Python), so the schema design carries over exactly. The `mcp-tools.md` surface is unaffected (it specifies tools, not a language).
- Doc reconciliation owed (separate pass, not blocking): strike "TypeScript" from meta-plan/architecture/spec; restate the package layout in Python-monorepo terms. Tracked with the broader spec-vs-DDL reconciliation.
- Maintainer fluency is now an explicit, recorded design input for this personal tool — relevant to future tooling choices where ecosystem maturity is otherwise a wash.
 
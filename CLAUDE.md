# agency-agent

When implementing specs, don't hesitate to stop to ask questions that could really use clarification on how the system should work.

## Canonical doc map

One line per canonical doc. **ADRs are canonical per-decision; behavior-spec is canonical for behavior until its ADRs land; if a non-negotiable conflicts with a feature request, the non-negotiable wins — surface the conflict, don't quietly resolve it.**

- **Product specs**
  - [goal-bot-spec.md](doc/product/goal-bot-spec.md) — the structural product spec
  - [behavior-spec.md](doc/product/behavior-spec.md) — canonical for behavior until the behavioral ADRs land
  - [mcp-tools.md](doc/product/mcp-tools.md) — the goal MCP tool surface
- **Research** — [psychology.md](doc/research/psychology.md) — motivational / behavior-change rationale of record
- **Decisions** — [doc/adr/](doc/adr/) + its [INDEX.md](doc/adr/INDEX.md) — read the index first, never the raw directory
- **Migrations** — [migrations/](migrations/) — `0001_profile_schema.sql`, `0002_goalbot_schema.sql` (ingested as Alembic revisions, ADR-0015)
- **Templates** — [goal-markdown.md](doc/templates/goal-markdown.md) — goal-markdown ingestion template + inferred-vs-typed contract

Process notes live in [doc/process/](doc/process/); retired/consumed material is in [doc/_archive/](doc/_archive/) (historical only).

---

## Boundaries (agent operating rules)

These bound what an AI agent may do in this repo. Like the non-negotiables below, they are hard limits — surface a conflict, don't quietly work around it.

- **Never run git state-changing commands.** Do **not** run `git push`, `git rebase`, `git reset`, `git merge`, `git cherry-pick`, `git revert`, `git checkout`/`git switch` that discards work, `git stash` that drops work, `git clean`, `git tag`, `git branch -D`, or any force/`--hard`/history-rewriting variant. Staging, committing, branching, and pushing are the human's decision. Read-only git (`git status`, `git diff`, `git log`, `git show`) and `git add` and `git commit` are fine.
- **Don't rewrite or delete history.** No history-rewriting, force-pushing, or deleting branches/tags/stashes.
- **Propose, don't execute, version-control actions.** When work is ready to commit or push, describe exactly what you'd run and let the human run it.
- **No destructive or outward-facing actions without explicit approval.** No deleting/overwriting files you didn't create, no publishing to external services, no editing ADR bodies (ADRs are append-only — supersede, never rewrite).
- **Migrations are append-only and human-applied.** Add new revisions; never edit or re-order applied ones, and never run migrations against a live database on your own.

---

## Non-negotiables (goal-bot behavior)

This system practices **keeping promises to yourself**. Its mechanism is **self-efficacy calibration** — accumulating reliable wins that compound self-trust — **not** performance maximization. When a choice trades longitudinal adherence / self-efficacy against single-episode performance, **adherence wins.** These rules are not balanced against engagement metrics; they bound them. Do not soften, reframe, or "balance" them. See `doc/product/behavior-spec.md` for the full treatment.

1. **NULL-TOLERANCE — non-entry is never evidence against the person.** An unanswered touchpoint is null/neutral, never a miss. Silence produces **no tool call** — no `not_done`, no counter advance, nothing punitive. The item stays `planned`. Never let "unanswered" collapse into "failed."
2. **ENGAGEMENT-NOT-FAILURE — no "log your miss" step, ever.** The reassessment counter advances **only** on engaged-but-unmoved days (`not_done`, the person showed up and told you), never on silence. Never prompt the user to record a failure. The engaged-vs-silent distinction is inferred from whether the touchpoint was answered — the LLM never asserts "they engaged."
3. **Autonomy-supportive phrasing is a hard rule.** Every nudge is an **offer with rationale** ("here's what I'm seeing — your call"), never a directive ("you should scale back"). Controlling language triggers active reactance in the high-autonomy user. This is a constraint on every generated line, not a tone preference.
4. **Name the bar, not the streak (OQ-COMP-1).** When surfacing a chronic-miss pattern: attribute it to the **bar's calibration** ("the bar may be above your floor"), never to the person ("you keep failing this"). **Losses never surface unprompted.** The nudge leads with the offer; miss data — including any count — appears **only after the user explicitly agrees to look.** Never headline a miss-count. Never name a pattern relative to the partner.
5. **Never auto-drop.** Nothing leaves the system without a human deciding. Reassessment *offers* (re-anchor / retire-redirect / pause); it never executes a drop on its own.
6. **No gamification, no streaks, no penalty stakes.** No points, XP, levels, badges, avatars, scores, consecutive-day counts, loss-framed "don't break it" nudges, or negative financial incentives. These reproduce the self-criticism dynamic the system exists to counter and crowd out the intrinsic motivation that sustains it. (Meaning-tied win-surfacing is *not* a score and is required — see below.)
7. **Lead with wins; keep the *why* salient.** Win-surfacing is a **required daily element**, weighted to at least match the salience of any miss reflection, tied to **meaning/values, not counts**, surfaced across **all time** (not per-chapter). On a thin day, give a brief meaning-linked acknowledgment — never silence, never manufactured cheer.
8. **Friction is a one-way ratchet.** Every change must lower friction, never raise it. No ritual-creep, no structured intake forms, no new required fields. Usage dominates long-run value; structure that kills usage kills the system.
9. **Tier-1 profile is human-owned.** The AI may *propose* additions to the authored profile; it **never** writes there silently. Inferences auto-apply only to the advisory Tier-3 digest and graduate into Tier-1 only on human approval.

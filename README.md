# agency-agent

[![CI](https://github.com/matthewncover/agency-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/matthewncover/agency-agent/actions/workflows/ci.yml)

A monorepo of personal agency tooling — **AI agents in service of personal agency**: systems for planning, tracking, and reflecting on the stuff of life — tasks, time, and goals. The packages share an identity primitive and a Postgres database, but they are separate tools used in separate contexts:

- **[goal-bot](packages/goal-bot/)** — the flagship: a goal accountability system that lives in Telegram group chats as a morning check-in. Most of this README (and most of [doc/](doc/)) is about it.
- **[task-tracker](packages/task-tracker/)** — an MCP server for task, sprint, time, and daily-log tracking, used on its own through the Claude UI (wired into a Claude Project). Goal-bot consumes it through a typed read-only client, but nothing about it requires goal-bot.
- **[profile](packages/profile/)** — the shared identity primitive (person + group supertype, so joint ownership is ordinary ownership) and the human-authored Tier-1 profile that other packages read.

Everything below describes **goal-bot** unless noted.

---

## goal-bot

A goal accountability system built around a shared Telegram bot. Every morning at 6am local time, it messages each person with a short check-in: here's what you committed to yesterday and what happened, and here's a realistic plan for today — want to lock it in?

That's the whole surface. One message a day. Everything else — the goal database, the versioning, the pattern-mining, the psychology — exists to make that one message good.

### The core idea: keeping promises to yourself

The system's deeper purpose isn't productivity, it's **practicing self-trust**. The locked-in daily plan is a promise; the morning-after review surfaces what made promises hard to keep.

Its foundational concept is the **95% Floor**: a goal's minimum bar should be the level you're *95% sure* you'd actually hit, given all the ways real life interferes. If you keep missing a goal, that's not a personal failure — it's evidence the bar was set too high, and the fix is recalibrating the bar, not blaming yourself. Both users are high-achievers who run hard on themselves, so the system is deliberately engineered *against* the report-card dynamic: misses are data, not verdicts.

That stance is encoded as hard rules, not tone preferences (see the non-negotiables in [CLAUDE.md](CLAUDE.md) and the full treatment in [doc/product/behavior-spec.md](doc/product/behavior-spec.md)):

- An unanswered morning is **null, never a miss** — silence is never evidence against the person.
- There is no "log your miss" step, ever. Reassessment triggers only on days the person *engaged* and the item still didn't move.
- Every nudge is an offer with rationale, never a directive.
- Chronic misses are attributed to the bar's calibration, never to the person — and miss data surfaces only after the person agrees to look.
- Nothing is ever auto-dropped; a human decides everything that leaves the system.
- No gamification: no points, streaks, badges, or penalty stakes.
- Win-surfacing is a required daily element, tied to meaning and values rather than counts.
- Friction only ever goes down — no ritual-creep, no new required fields.

### How it works

**The morning ritual.** One touchpoint per person per day. It opens by reviewing yesterday — framed as "what shifted?", not "did you fail?" — and this is when results get logged (yesterday's step count doesn't exist until yesterday is over; the "day" runs to the 6am local boundary). Then it proposes a **smart subset** for today: daily items, whatever's due before a weekly quota breaks, overdue one-offs and carry-overs — trimmed down on demanding days so the plan stays achievable. You can reshuffle or ask for the full list, then lock in. If you say nothing, the suggestion quietly counts as the plan — no nagging, no timers.

**A rich goal model.** Goals combine orthogonal dimensions rather than a single "type": recurrence (daily; quota like "gym 3×/week"; rotation like push → rest → pull with a pointer that advances only on completion; interval; fixed-schedule; accumulation toward a chapter total; one-off) × completion type (binary, quantity, duration) × ownership (either person, or the household as a group). Each goal can carry both a **need** version (the 95%-Floor minimum) and a **want** version (the stretch).

**Versioned history that never lies.** Goals are versioned, and each day's plan pins the exact version committed to. If a step goal was 6,000 in June and later rises to 8,000, June's wins stay wins — raising the bar never retroactively turns past successes into failures.

**Chapters.** Goals live inside named goal-setting blocks, each with its own dates and optional theme, owned by a person or jointly.

**Markdown authoring.** Goals are written as loose markdown (in Obsidian) — bar, stretch, why, anticipated obstacles — and an AI ingestion layer parses them into structured records, writing IDs back so re-ingesting updates rather than duplicates. The database is the source of truth; markdown is a working copy. See [doc/templates/goal-markdown.md](doc/templates/goal-markdown.md).

**Three-tier memory.**
- **Tier 1 — authored profile.** Human-owned prose (identity, priorities, schedule, personality, known patterns). The AI may propose additions; it never writes here silently.
- **Tier 2 — observations.** Append-only raw events: the "what shifted" reflections and the friction log. Evidence, not conclusions.
- **Tier 3 — insights digest.** An AI-maintained, explicitly advisory "patterns I'm noticing" layer ("workouts slip the day after poor sleep"). Insights graduate into Tier 1 only with human approval.

**Gentle recalibration, never punishment.** When something slides for about a week *of engaged days*, the bot offers — never dictates — a reassessment: re-anchor the bar to the 95% Floor, pause the goal, or (for one-offs only) drop it. The heavy-day trim caps optional extras on physiologically demanding days (low recovery or short sleep, via Whoop data from task-tracker's daily logs) while never touching needs — which are safe to protect by construction, since their bars were calibrated to survive bad days.

---

## Architecture

Three Python packages, one shared Postgres database as the source of truth (one schema per package):

- [packages/profile/](packages/profile/) — identity supertype and the Tier-1 authored profile.
- [packages/goal-bot/](packages/goal-bot/) — the goal domain: chapters, versioned goals, daily plans, the morning ritual assembly, Tier-2/3 memory, and the goal-markdown ingestion MCP.
- [packages/task-tracker/](packages/task-tracker/) — standalone task/sprint/time/daily-log MCP server; supplies goal-bot the heavy-day daily signal and goal candidates at chapter-setting time via a typed read-only client.

Cross-package access goes through published ports, never raw cross-schema SQL. Migrations are append-only Alembic revisions in [migrations/](migrations/). Design decisions are recorded as append-only ADRs — start at [doc/adr/INDEX.md](doc/adr/INDEX.md).

## Doc map

| Doc | What it is |
|---|---|
| [doc/product/goal-bot-spec.md](doc/product/goal-bot-spec.md) | The structural product spec (goal-bot) |
| [doc/product/behavior-spec.md](doc/product/behavior-spec.md) | Canonical behavior spec (goal-bot) |
| [doc/product/mcp-tools.md](doc/product/mcp-tools.md) | The goal MCP tool surface |
| [doc/research/psychology.md](doc/research/psychology.md) | Motivational / behavior-change rationale of record |
| [doc/adr/INDEX.md](doc/adr/INDEX.md) | Decision index (read this, not the raw directory) |
| [doc/templates/goal-markdown.md](doc/templates/goal-markdown.md) | Goal-markdown authoring template |
| [packages/task-tracker/docs/spec.md](packages/task-tracker/docs/spec.md) | task-tracker's own spec (schema, tools, architecture) |

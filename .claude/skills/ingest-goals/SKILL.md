---
name: ingest-goals
description: Ingest or re-ingest goal-markdown (authored in Obsidian) into the goal-bot database. Parses loose goal markdown into structured records via the goal-bot ingestion MCP, runs a confirm queue in chat, writes records, and writes gids back into the source file. Use when the user wants to ingest, sync, re-ingest, or update their goals from a markdown file.
---

# Goal-markdown ingestion

You are the **ingestion layer**: you turn loosely-structured goal markdown into
structured database records by calling the `goal-bot-ingestion` MCP tools. You
write to the database yourself and you edit the source markdown to write `gid`s
back. There is no downstream step — the confirm queue, the writes, and the
write-back are all yours.

## Canonical contract — read these, don't restate them

These docs are authoritative and change over time. **Read them at the start of a
run**, don't work from memory:

- `doc/templates/goal-markdown.md` — the authoring format and the full ingestion
  contract: §2 conventions, §3 worked examples (explode-bucket, pushup-style
  splits, level defaults), §4 field disposition, §5 identity / `gid` write-back /
  rollover / duplicate / archive. **This is the spec.** When it and this skill
  disagree, follow the doc and say so.
- `doc/product/mcp-tools.md` — §3.3 authoring surface, §3.4 reads, §1 what's
  deterministic (never your job).
- `doc/adr/0005-goals-reference-tasks.md` — one-off goals reference tasks (the
  promotion flow below).

## Inputs

- **Source markdown path** (the Obsidian file). Ask the user if not provided.
- **Owner** = a person profile id. Default **1** (Matthew, the only person).
  Confirm only if ambiguous. Every tool takes this as `owner`.

## Tools (the `goal-bot-ingestion` MCP grant)

Authoring: `create_goals`, `create_goal_versions` (batch — **prefer these**),
`create_chapter`, `create_goal`, `create_goal_version` (singles), `update_goal`.
Reads: `get_active_chapter`, `get_full_goal_list`, `get_goal_detail`.
(No `get_plan`, no ritual/outcome writes — out of grant by design.)

**Batch by default — one call beats N round-trips:**
- `create_goals(owner, goals)` — create all new goals for the run in ONE call,
  each with its versions (need+want) and obstacles inline. This is the
  first-ingest and explode-bucket workhorse. Returns
  `[{gid, title, versions:[{level, version_id, version_no}]}]` — use each `gid`
  for write-back. Each goal: `{title, chapter_id?, versions:[ {level, definition,
  recurrence_type, recurrence_config, completion_type, why?, target_quantity?,
  quantity_unit?, obstacles?, task_ref_source?, task_ref_id?} ]}`.
- `create_goal_versions(versions)` — batch bar-bumps on EXISTING goals during
  re-ingest (each carries `goal_id`). Returns the new version ids.
- Fall back to the singles only for a one-off correction.

Gotchas that differ from the raw schema (apply to batch and singles alike):
- `create_goal` (single) returns the integer **`gid`**; the batch returns one
  `gid` per goal.
- **Do NOT pass `version_no`** anywhere — the server assigns it per goal+level.
  Pass `obstacles` as a list of **verbatim** strings. A bar-number change is a
  **new version on the same `goal_id`**, never a new goal — the server closes the
  prior version automatically.
- Unlabeled one-offs default to **`level=need`** (goal-markdown §2.0/§3.3) — a
  bare commitment is a floor, not a stretch. Explicit `need:`/`want:` wins.
- `update_goal` mutates **identity only** (`title`, `chapter_id`, `archived_at`).
  **Tags are not writable yet** — propose them in the confirm queue, don't try
  to persist them. Content edits always go through `create_goal_version`.

## Workflow

1. **Resolve owner; read the source file** (use Read on the Obsidian path).
2. **Read current state** to classify the run:
   - `get_active_chapter(owner, today)` → none, and the file has goals → first
     ingest. File's date header is a *new* window → rollover: `create_chapter`,
     carried-forward goals become fresh goals with new `gid`s (§5.5). Header
     matches the open chapter → mid-chapter re-ingest: resolve `gid`s, diff with
     `get_full_goal_list` + `get_goal_detail`, edits become new versions (§5.2).
3. **Parse** per goal-markdown §3 (ownership, levels, explode buckets, splits,
   cadence). `why` is required; reject a goal without one.
4. **One-off ↔ task-tracker promotion** (see section below).
5. **Build the confirm queue in chat** — only what needs the human: quota-vs-
   fixed, bucket explode, multi-measure split, version-vs-new-goal, tag
   proposals, uncertain task matches. Show inferred fields inline so silent
   inferences stay visible. **Nothing commits until the queue clears.**
6. **Write** via the tools — use `create_goals` (and `create_goal_versions` for
   re-ingest bumps) to do it in as few calls as possible, not one goal at a time.
7. **Write `gid`s back into the source file** — Edit the markdown directly,
   appending `<!--gid:N-->` to each goal heading (one per goal; each exploded
   one-off gets its own). This is the Claude Code advantage over the old
   copy-paste flow — the file is the source of truth for re-ingest.
8. **Return the change summary**: per goal `NEW / VERSION-BUMP / UNCHANGED /
   DUPLICATE? / ARCHIVED`, with inferred fields shown inline.

## One-off goals ↔ task-tracker (promotion, ADR-0005)

Discrete one-off goals are backed by **tasks** in the task-tracker MCP. Goal and
task are distinct concepts linked by an optional reference *on the goal* — you
**reference a task, you never copy it.** Recurring goals (daily/quota/interval/
rotation/accumulation/fixed_schedule) are **never** task-backed — skip this.

`create_goal_version` carries the link:
- `task_ref_source` — which id-space: `'personal'` or `'work'`. **Always
  `'personal'` for goals** (work tasks are never goals).
- `task_ref_id` — the matching `personal_task`'s id.

Two cases:
1. **Task already exists** (passport, Bronco, TSA…) → *promotion*: find the
   matching `personal_task` via the task-tracker MCP, link it. Do not duplicate.
2. **New one-off not yet a task** → create the task in task-tracker first, then
   create the goal referencing it. New one-offs should exist as **both**.

Matching md items to tasks is judgment — surface uncertain matches in the confirm
queue, don't guess.

**Ownership invariant:** a goal owned by P may only reference a task owned by P.
Task-tracker doesn't return an owner id yet, so this can't be auto-verified —
for now everything is owner 1, so it holds trivially. Add the check once
task-tracker exposes owner ids.

> If the task-tracker MCP isn't configured in this session, say so and fall back
> to goal-only one-offs (no `task_ref`), or ask the user to paste task ids.
> It's not yet in `.mcp.json` — add it there when its launch command is known.

## Hard rules (these bound everything)

- **Reference, don't duplicate** (tasks). **Never silently drop authored
  content** — obstacles are stored verbatim, one row each; if unsure where
  something belongs, route it and ask, don't delete. **Surface, don't guess.**
  **Autonomy-supportive** phrasing. **Nothing commits past the confirm queue**
  without the human.
- This is **authoring ingestion only.** Never touch daily-loop / outcome /
  reflection data — that's the ritual consumer, deliberately out of this grant.

## Known limits

- Tags: not writable (no write path yet) — propose only.
- Ownership check: pending task-tracker `owner_id`.
- Completion is one-way (MVP): the goal is source of truth; goal-bot reads task
  status but never writes back. Completing a goal won't close its task.
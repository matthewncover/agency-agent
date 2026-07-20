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
  Claude cannot read `~/Documents` (macOS TCC) — if the path is in the vault,
  have the user copy it somewhere readable and paste the gid-marked copy back.
- **Owner** = a person profile id. Default **1** (Matthew). Confirm only if
  ambiguous. Every tool takes this as `owner`.

## Step 0 — verify the database target (ALWAYS, before anything else)

MCP servers read `.env` **only at launch**; the file and the running server
drift silently. Never assume — verify, show the user, get a nod:

1. State which DB `.env`'s `DATABASE_URL` points at (dev, or prod via the
   `localhost:5433` ssh tunnel). If it was just changed, the user must `/mcp`
   → reconnect **both** `goal-bot-ingestion` and `task-tracker` (they resolve
   `.env` independently — a mismatch between them writes goals and tasks to
   different databases).
2. Prove it with data: `get_active_chapter(owner, today)` and a known-task
   probe (`search_tasks` for something that exists only in the intended DB).
   State the evidence ("no chapter → fresh prod") before the first write.
3. **Prod sessions**: confirm the ssh tunnel is up first; at session end,
   remind the user to revert `.env` to dev and reconnect again — anything that
   reads `.env` (pytest's live fixture, `just seed`, `just toy-reset`) hits
   real data while it points at prod.

## Tools (the `goal-bot-ingestion` MCP grant)

Authoring: `create_goals`, `create_goal_versions` (batch — **prefer these**),
`create_chapter`, `create_goal`, `create_goal_version` (singles), `update_goal`.
Rotation groups (ADR-0016): `create_rotation_group`, `archive_rotation_group`,
`list_rotation_groups`.
Reads: `get_active_chapter`, `get_full_goal_list`, `get_goal_detail`,
`get_goals_for_chapter`.
Deterministic goal-setting / re-ingest ops (B2): `propose_candidates`,
`diff_chapter`, `rollover`, `check_goal_scope`.
(No `get_plan`, no ritual/outcome writes — out of grant by design.)

**Identity is the tools' job, not yours.** `diff_chapter` / `rollover` /
`check_goal_scope` decide new-vs-version, what carries forward, and scope flags
*deterministically* behind the boundary. You parse loose markdown and run the
confirm queue; you do **not** re-identify goals by eyeballing content (the
failure mode goal-markdown §5.1 exists to avoid). Feed the tools structured
input, act on what they return.

- `propose_candidates(owner)` → `{goals:[past goals], tasks:[open tier-2/3
  personal]}`. Use this to seed goal-setting — propose *from* it; don't rely on
  recall or re-query. Work tasks never appear (ADR-0005).
- `diff_chapter(chapter_id, parsed)` — `parsed` is a list of
  `{gid?, title, definition, recurrence_type, target_quantity?}`. Returns one
  classification per goal: `new` / `version_bump` / `unchanged` / `ambiguous`
  (version-vs-new-goal, `default: version_bump`) / `unknown_gid`, plus
  `archived` for any recorded goal that vanished from the markdown (§5.4).
- `rollover(owner, start, end, carried, label?, preamble?)` — opens the new
  chapter, mints `carried` (`[{title, versions:[...]}]`) as **fresh** goals
  scoped to it, and archives the prior chapter's goals. No cross-chapter
  lineage (ADR-0013). Returns `{chapter_id, new_goal_ids, archived_goal_ids}`.
- **Chapter preamble** (goal-markdown §2.1, v0.7): free prose between the date
  header and the first `###` heading — theme / focus / parked domains. Pass it
  verbatim as `preamble` to `create_chapter` or `rollover`; never paraphrase
  it, never drop it silently. Docs are one-per-owner; a combined doc still
  ingests via the ownership headings.
- **recurrence_config conventions (v0.8 — the deterministic layer reads these
  exact keys; wrong keys silently break scheduling):**
  - one-off with a due date: `{"target": "YYYY-MM-DD"}` — this is what makes it
    auto-surface near/overdue. A one-off without `target` is full-list only;
    if the author wrote a `target:` line, it MUST land in the config.
  - quota: `{"per_window": N, "window": "week"}` — `per_window`, NOT `count`
    (`count` is a read-side legacy alias only; never author it).
- `check_goal_scope(goal_owner_id, chapter_id)` → `{confirm_required, reason}`.
  Call before writing a goal into a chapter (see the confirm queue).

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
2. **Parse** per goal-markdown §3 (ownership, levels, explode buckets, splits,
   cadence). `why` is required; reject a goal without one. This is your job —
   the loose-markdown → structured-record step.
   **Then lint before anything interactive** — one consolidated gap report, not
   gaps discovered mid-flow: every goal missing a `why` (including want-only
   goals and `why: see below`-style dangling references), file header dates vs
   what the user has said about the window, items that look dead/already
   decided, unlabeled levels about to default to `need`, owners that don't
   exist yet (provisioning needed). Get all answers in one round-trip.
3. **Classify the run by the file's date header** vs `get_active_chapter(owner,
   today)` — and let the tools resolve identity, don't diff by hand:
   - **Header is a new window** → **rollover.** Call `rollover(owner, start,
     end, carried, label?)` with the carried-forward goals; it mints fresh
     `gid`s in the new chapter and archives the prior one (§5.5). Do **not**
     hand-roll `create_chapter` + archive.
   - **Header matches the open chapter** → **mid-chapter re-ingest.** Call
     `diff_chapter(chapter_id, parsed)` and act on its classifications (step 5).
     Don't re-derive new-vs-version yourself (§5.2).
   - **First ingest** (no chapter, file has goals) → `create_chapter`, then
     `create_goals`.
4. **One-off ↔ task-tracker promotion** (see section below). For goal-setting
   from scratch, seed candidates with `propose_candidates(owner)`.
5. **Build the confirm queue in chat** — only what needs the human. Route the
   tools' outputs *into* the queue; don't re-decide them:
   - `diff_chapter` → `ambiguous` **is** a version-vs-new-goal item (offer the
     `default: version_bump`); `archived` → surface "archived: X, Y — unarchive
     if unintended" (§5.4); `unknown_gid` → surface, never silently write.
   - Before writing a goal into a chapter, call `check_goal_scope(goal_owner_id,
     chapter_id)`; if `confirm_required`, add the flag (group-owned goal in an
     individual's private chapter, ADR-0013) with its `reason`.
   - Plus the parse-side calls: quota-vs-fixed, bucket explode, multi-measure
     split, tag proposals, uncertain task matches.
   - **Coupled rhythm → rotation group (ADR-0016).** A `rotate: [a, rest, b,
     rest]` line is an explicit group instruction. Also *propose* a group
     (confirm, never silent) when a multi-measure split yields goals whose
     phrasing implies one alternating rhythm ("alternating", "then", shared
     "every N days" on movements trained on different days) — two independent
     interval clocks WILL drift onto the same day; that's the failure this
     feature exists for. Never model the coupled case as two bare intervals
     without at least offering the group.
   Show inferred fields inline. **Nothing commits until the queue clears.**
6. **Write** via the tools — `create_goals` for new goals, `create_goal_versions`
   for the `version_bump` classifications, `rollover` for a new window. Batch;
   don't write one goal at a time. **Rotation groups write last** (they need the
   member `gid`s): `create_rotation_group(owner, name, sequence)` with entries
   `{"goal_id": N}` / `{"rest": true}`. Members keep their natural recurrence
   (e.g. `interval`) on their versions — it goes inert while the group is
   active and is the graceful fallback if the group is archived.
   **At rollover, groups go stale by construction** (they reference the prior
   chapter's goal ids): `list_rotation_groups(owner)` → for each group whose
   members were carried forward, `archive_rotation_group` the old one and
   re-create it against the new `gid`s, preserving the sequence order.
7. **Write `gid`s back into the source file** — Edit the markdown directly,
   appending `<!--gid:N-->` to each goal heading (one per goal; each exploded
   one-off gets its own). A **split goal** (one authored block → N goals, e.g.
   pushups/pull-ups) gets all its gids on the shared heading, labeled:
   `<!--gid:9 pushups--> <!--gid:10 pull-ups-->`. If a rotation group was
   created from phrasing (no authored `rotate:` line), write the `rotate:` line
   into the section too, so the file round-trips. Items deliberately NOT
   ingested get no gid — tell the user to delete them from the source, or the
   next re-ingest re-surfaces them as new candidates. This is the Claude Code
   advantage over the old copy-paste flow — the file is the source of truth
   for re-ingest.
8. **Return the change summary** — build it straight from `diff_chapter`'s
   output (`NEW / VERSION-BUMP / UNCHANGED / ARCHIVED`, plus any `ambiguous`
   the human resolved), with inferred fields shown inline. Don't re-classify.

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
queue, don't guess. Two different jobs, two different sources:

- **Goal-setting proposals** → `propose_candidates(owner)` (open tier-2/3 only,
  by design).
- **Link-target matching** (does this one-off already have a task?) → the
  candidates list is NOT enough: tier-1 and done/nuked tasks are hidden from it,
  and they're often exactly the matches (a one-off may already be complete).
  While the personal-task corpus is small (≲ a few hundred), pull the full list
  once (`search_tasks` with `include_done=true` on broad probes, or a direct
  listing) and match by reading it — keyword-guessing misses synonyms
  ("bronco" vs "Vehicle registration transfer"). If the corpus outgrows one
  read, fall back to multiple synonym searches per item, always with
  `include_done=true`, and say which items you could not confidently match.

**Ownership invariant:** a goal owned by P may only reference a task owned by P.
Task-tracker is now owner-scoped (B1): `propose_candidates` and the task client
only ever return tasks for the given owner, so a candidate from that list already
satisfies the invariant. Still verify any task id the human pastes in by hand
belongs to the owner before linking.

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
- Ownership check: task-tracker is owner-scoped (B1), so list-sourced candidates
  are safe; only hand-pasted task ids still need a manual owner check.
- Completion is one-way (MVP): the goal is source of truth; goal-bot reads task
  status but never writes back. Completing a goal won't close its task.
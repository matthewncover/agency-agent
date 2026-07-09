# Goal MCP — Tool Surface (minimum set)
 
> **Doc:** `doc/product/mcp-tools.md` · **v0.1** · status: draft, design rule + tool surface settled; three behavioral contracts ride along; two items deferred.
> **Role:** Define the **goal MCP tool surface** — the operations the conversational LLMs may call against goal-bot state. Input: `goal-bot-spec.md` v0.5, `doc/_archive/architecture.md` v0.3 (esp. §5), `goal-markdown.md` v0.4 (§5 ingestion contract), `synthesis-inbox.md` (behavioral decisions). This doc specifies the *tool boundary*, not goal-bot's internal logic; deterministic operations named here as "Python, not a tool" are owned by goal-bot and described only enough to fix the boundary.
> **Companion:** the context-assembly mechanism that *feeds* these tools (and the long-chat windowing puzzle, §6) lives in the agent runtime, not here — this doc is MCP-orthogonal to it but names it as unresolved.
 
---
 
## 1. The design rule (read first)
 
**The MCP surface is the set of operations that genuinely require the LLM's judgment or the user's stated input. Everything deterministic is goal-bot Python that the agent runs, not a tool. Tools are where conversation touches state.**
 
This is the single rule that determines whether any proposed tool belongs. It generalizes the position architecture §5 already takes (candidate-gathering is deterministic, surfaced to the LLM as a prepared list; the LLM never issues the selection). Applied across the whole surface, it keeps the tool count small *by construction* and draws a bright line a future contributor can apply without re-litigating.
 
**Deterministic — Python, never a tool:**
- Profile/kind resolution (person vs. group), member enumeration — the LLM is handed a already-resolved `owner` and never reasons about `kind` (the Profile port, ADR-0012, is called in the backend).
- Smart-subset selection (the §3 3-bucket heuristic) and the lighter-day trim.
- Budget math (quota sessions remaining vs. days left).
- Pointer advancement for `interval`/`rotation` on completion (`goal_state`).
- Shared-state propagation for group goals ("done for both").
- Derived wins (from done items).
- Carry-over counting and the ~1-week reassessment trigger.
- Version-by-date resolution (which `goal_version` was effective on a past date, for pinning/backdating).
- Yesterday's results and the win surface for the morning turn — **injected into context, not pulled by tool.**
**Judgment- or input-bearing — a tool:**
- Anything that records what the **user actively reported** (an outcome, a reflection, a manual win, progress).
- Anything that **commits** a plan the user assented to (lock-in).
- Anything **authoring** (create/version/lifecycle a goal or chapter) — held by the ingestion consumer, scoped away from the ritual consumer except where §3 reassessment requires it.
- On-demand **reads** the LLM needs mid-conversation that aren't already injected (full list override, a past day's plan, a goal's detail to diff against).
**Corollary — non-entry is never a tool call.** Per NULL-TOLERANCE / ENGAGEMENT-NOT-FAILURE (synthesis-inbox; spec §10): a touchpoint the person never answered produces **no** `log_outcome` call. Silence is the *absence* of a tool call, handled by goal-bot's carry-over logic — never an asserted `not_done`. This keeps "non-entry is never evidence against the person" structurally true rather than a rule the LLM has to remember (§4.1).
 
---
 
## 2. Two consumers, scoped grants
 
One MCP server; the grant is scoped per consumer, the same way the ritual LLM doesn't hold the task MCP (architecture §5).
 
| Consumer | Where | Holds |
|---|---|---|
| **Morning-ritual LLM** | Telegram, agent-driven | the ritual write surface (§3.1), reassessment lifecycle (§3.2), on-demand reads (§3.4). **Plus** `create_goal_version` scoped to inline re-anchoring only (§3.2, deliberate — see note). |
| **Ingestion LLM** | separate Claude chat (per `goal-markdown.md`) | the authoring surface (§3.3) + shared reads (§3.4). Does **not** hold the daily-loop write tools. |
 
The ritual LLM should not silently rewrite goal definitions during a check-in — hence the authoring surface is the ingestion consumer's, with one deliberate exception (re-anchoring) recorded in §3.2.
 
---
 
## 3. The tools
 
Signature conventions: `owner` is a resolved person-or-group profile id supplied by the backend (the LLM never constructs or branches on it). `date` defaults to the current plan-date (6a-local boundary, spec §8) when omitted. Side effects that touch deterministic state (pointers, counters, shared state) are listed because the tool *triggers* them, even though goal-bot *computes* them.
 
### 3.1 Morning-ritual write surface
 
**`log_outcome(daily_plan_item_id, status, quantity_actual?)`**
Records an outcome the user **actively reported** for a planned item.
- `status ∈ {done, partial, not_done}` — the user-asserted terminal states only. `planned`/`carried_over` are system states, never passed here.
- `not_done` means *"engaged and it didn't happen"* — the person told you. It is **the only status that advances `carry_over_count`** (§4.1). Silence never reaches this tool.
- For `quantity` goals, `quantity_actual` carries the number (OQ-8, entered the following morning by the owner). `partial` is informational — records the actual for pattern-mining, does **not** tick a quota counter (spec §5).
- **Side effects (goal-bot):** advances `goal_state.last_completed_at` / `rotation_index` for pointer goals on `done`; propagates shared completion for group goals ("done for both") when called on a member's fanned-out item (§3, OQ-9).
- **Backdating:** allowed via the item's own `plan_date` (the item already carries its date; no "yesterday" assumption is baked in). Backdating pins the version effective *on that date*, not today's (deterministic version-by-date lookup). **Restricted to non-pointer goals** (binary/quantity/duration) for MVP — backdating an `interval`/`rotation` goal would require pointer recomputation from history (§5, deferred). Manual re-pointing is a separate explicit tool (§3.2 `set_rotation_pointer`), not a backdated log.
**`log_progress(goal_id, amount, unit?, date?)`**
Accrues progress toward an `accumulation` goal's chapter target (4h painting; 12 books; $5,000).
- **Not** a terminal-state write — no done/not_done. goal-bot sums entries and computes whether the chapter target is met.
- **No carry-over interaction.** Accumulation goals are **exempt from the ~1-week reassessment nudge entirely** — "didn't paint today" is structurally not a miss (§4.3). This is a behavioral commitment, stated so it isn't lost.
- **Accumulation-in-a-plan:** when an accumulation goal surfaces in a daily plan, the plan item is a *prompt to engage*; engaging means calling `log_progress`, and the item's status **derives** from whether progress was logged — there is no separate `log_outcome` call for it. (Prevents a double-write where both tools touch the same accumulation goal.)
**`record_reflection(daily_plan_item_id?, what_shifted?, friction_text?)`**
The "what shifted" reflection and/or an observed-obstacle row — "the real gold" (spec §3, §7b Tier-2).
- Writes `daily_plan_item.what_shifted` and/or a `friction_log` row. `daily_plan_item_id` optional so friction can be logged unattached to a specific item.
- Single tool (friction not split out) — confirmed.
**`lock_in_plan(daily_plan_id, items[], explicit=true)`**
Finalizes a plan the user explicitly assented to. Sets `locked_in_at`, `lock_was_explicit`, and pins `goal_version_id` per item.
- `items[]` carries, per goal: inclusion and **`committed_level`**. `committed_level` defaults to **`need`** when unspecified (commit to the floor unless you reach); for a goal with no need version (want-only, e.g. §3.4 volleyball) it defaults to the goal's only level. This *selects which `goal_version_id` is pinned* — it is **not** a per-day need→want demotion (OQ-3 fixed level as a goal-definition property; the stale §3 "move items between needs and wants" prose should be corrected to this — see §4.2).
- **Only called on an explicit lock.** The implied-lock case writes nothing here (§4.2).
**`add_win(owner, text, goal_id?)`**
Manual win entry, any time (spec OQ-13). `goal_id` optional. Derived wins are goal-bot-internal, not this tool.
 
### 3.2 Reassessment lifecycle (ritual, fired when an injected nudge prompts the user)
 
Per spec §3: never auto-drop; the human chooses; the bot surfaces the option after ~a week.
 
**`set_goal_lifecycle(goal_id, state)`**
One tool spanning the two tables lifecycle lives in, so the LLM doesn't carry the schema detail:
- `archive` / `unarchive` → writes `goal.archived_at` (one-off drop, D-5 retire/redirect, md-removal reversal).
- `pause` / `activate` → writes `goal_version.lifecycle` (the `paused` on-ramp, dormant-not-dropped).
(Annoyance recorded: `archived` is a `goal` column, `paused` is a `goal_version.lifecycle` value. The tool hides that split behind one verb-per-state surface.)
 
**`create_goal_version(...)`** — *held by the ritual LLM scoped to inline re-anchoring only.*
Re-anchoring a recurring goal's bar to the 95% Floor during reassessment is mechanically a new version at a lower target (spec §3). **Deliberate exception:** the ritual LLM holds this *only* for that path, accepting the wider mutation surface for the conversational LLM as an MVP tradeoff (Matthew: "manual anyway, get it right, defer improvements"). Recorded as chosen, not leaked — it contradicts the architecture's "ritual LLM doesn't author" instinct, and a future reader should see the decision. Full signature in §3.3.
 
**`set_rotation_pointer(goal_id, position)`**
Manual pointer set with no completion attached — "today is a push-up day." A rare, explicit correction affordance, **not** part of the daily loop and **not** a side effect of any other tool (the LLM must never nudge the pointer implicitly). Dedicated on purpose. Pairs with the non-pointer-backdating restriction (§3.1): you correct the pointer directly rather than backdating a workout.
 
**`set_rotation_group_pointer(group_id, position)`** *(ADR-0016)*
The same correction affordance for a rotation **group**'s shared pointer. Same rules: no completion attached, never a side effect. (Group pointer *advancement* on `done` is deterministic Python per §1 — computed from the **surfaced** entry via the date-aware walk, never a tool.)
 
### 3.3 Ingestion authoring surface (ingestion LLM)
 
Per `goal-markdown.md` §5. The `gid` write-back is **not** a tool — it is the return value of `create_goal` surfaced in the ingestion chat's re-marked markdown output (§5.1).
 
**`create_chapter(owner_profile_id, start_date, end_date, label?)`** — rollover / new window (§5.5).
 
**`create_goal(owner_profile_id, chapter_id?, title) → gid`** — returns the opaque id for write-back. `chapter_id` nullable (chapter-less goals persist across windows, ADR-0013).
 
**`create_goal_version(goal_id, level, definition, recurrence_type, recurrence_config, completion_type, target_quantity?, quantity_unit?, why, obstacles[])`**
The authoring workhorse: new goal bars, bar changes (new version, same id — OQ-5/14), and the need+want pair on create. `why`/`obstacles` written to all active versions on ingest (template §4). A bar-number change is always a new version; large content change is surfaced as version-vs-new-goal, never guessed (§5.2).
 
**`update_goal(goal_id, {title?, tags?, chapter_id?, archived_at?})`**
Mutates the **identity row only**. Tags (the §4 confirmed-tagging step), title, chapter reassignment, archive flag.
- **Hard boundary:** `update_goal` must **never** grow a `definition`, `recurrence`, `level`, or `completion` param. Identity-row mutation vs. content mutation is the whole point of the identity/version split — content edits go through `create_goal_version`. Smuggling content fields into `update_goal` breaks versioning. (This is the one boundary in the doc most likely to erode under "just add a field"; it's load-bearing.)

**Rotation groups (ADR-0016)** — authored structure from the template's `rotate:` line; groups are schedulers, not goals.
- **`create_rotation_group(owner, name, sequence)`** — `sequence` entries `{"goal_id": N}` | `{"rest": true}`; member refs validated at write (exist, owner-owned, unarchived, not already in an active group).
- **`archive_rotation_group(group_id)`** — authoring removal / rollover staleness; members degrade back to self-scheduling.
- **`list_rotation_groups(owner)`** — the re-ingest reconciliation read (groups reference chapter-scoped `gid`s and go stale at rollover, ADR-0013).
### 3.4 Shared reads
 
Reads the LLMs need mid-conversation that aren't already injected.
 
**`get_full_goal_list(owner)`** — the §3 "show me the full list" override of the injected smart-subset. Returns the owner's **active-chapter goals ∪ that owner's chapter-less (`chapter_id = null`) goals**, minus archived/paused. *Not* "most recent chapter only" — that would silently drop the null-chapter goals the nullable FK exists to support (ADR-0013).
 
**`get_goals_for_chapter(chapter_id, owner?)`** — ingestion diff + surfacing. `owner` optional: omitted returns all goals in the chapter (incl. a group-owned chapter's); set filters to that owner.
 
**`get_goal_detail(goal_id)`** — current versions + state, for diffing on re-ingest (§5.2/5.3) and ad-hoc recall.
 
**`get_plan(owner, date)`** — fetch a specific day's plan items. Needed for backdating an older day (the LLM holds today's items via injection, but not an arbitrary past day's). Also one of the deterministic reads the agent uses to *assemble* morning context — but as a tool it exists for the on-demand past-day case.
 
**`get_active_chapter(owner)`** — resolve the current chapter for the owner; used by reads above and by ingestion to tell mid-chapter re-ingest from rollover (§5.5).
 
---
 
## 4. Behavioral contracts that ride on the tools
 
These are not tool shapes — they are semantics the tools must not violate. Stated here because the tool and the contract are coupled and a future change to one can silently break the other.
 
### 4.1 The status enum + carry-over (ENGAGEMENT-NOT-FAILURE / NULL-TOLERANCE)
`daily_plan_item.status ∈ {planned, done, partial, not_done, carried_over}`.
- **never-touched** (touchpoint unanswered) → item stays `planned`, neutral, **does not advance `carry_over_count`**. Produces no `log_outcome` call (§1 corollary).
- **engaged-but-unmoved** (person showed up, item didn't move) → `not_done` via `log_outcome`. **The only path that advances `carry_over_count`**, which drives the ~1-week reassessment nudge (spec §3).
- `carried_over` tracks presence-in-the-loop across days; the *counter* ticks only on engaged misses.
- The engaged-vs-silent distinction is **inferred by goal-bot from whether the touchpoint was answered** — the LLM never asserts "they engaged." This is what makes the null-tolerance invariant structural.
- **Guardrail:** never let "unanswered" collapse into `not_done`. A future "log your miss" step is forbidden (friction + the self-criticism ritual the system is built against).
### 4.2 Implied lock is a read-time interpretation, not a deferred write
Provisional plan is persisted on send (OQ-2). If no explicit lock happens, **nothing is written** the next morning — the provisional rows already exist. The next morning's retrospective **treats the existing provisional plan as what was committed**, regardless of whether `locked_in_at` is null.
- `lock_in_plan` is called **only** on an explicit lock.
- `lock_was_explicit` is **pattern-mining data** (does this person lock, or coast on suggestions?), **not a control-flow gate.**
- **Guardrail:** the retrospective must not branch `if locked_in_at is null: skip` — that breaks the implied-lock contract. An unlocked provisional plan and an explicitly-locked one are both "what you committed to."
- **Stale prose to fix:** spec §3's "move items between needs and wants" predates OQ-3 and implies a per-day reclassification the data model removed. What survives is per-day *level selection* for a both-bars goal, expressed as `committed_level` in `lock_in_plan`. Correct the §3 wording in the behavioral pass.
### 4.3 Accumulation is exempt from miss semantics
`log_progress` accrues; there is no per-day pass/fail for an accumulation goal, so it never advances `carry_over_count` and never triggers the reassessment nudge. An accumulation goal in a daily plan derives its item status from logged progress (§3.1), never from a separate outcome call.
 
---
 
## 5. Deferred / out of scope
 
- **Pointer-goal backdating.** Backdating `log_outcome` is MVP-restricted to non-pointer goals (binary/quantity/duration). Backdating `interval`/`rotation` needs pointer recomputation from completion history; deferred. Manual `set_rotation_pointer` covers the live correction need in the meantime.
- **Context windowing for the long-lived shared chat (the open puzzle).** MCP-orthogonal but unresolved, recorded here so it isn't lost. It is an **agent-runtime** concern (the generic loop owns "build context," architecture §3), *not* an MCP concern. The three-tier memory model already carries most of the load: the morning turn works from curated Tier-1 + compressed Tier-3 + today's injected plan + a thin slice of very recent raw events — **it does not re-read the whole chat** (spec §7b). What remains undefined: the **width of the thin recent slice** (one day? two?) and the **reset cadence** (when context resets, what survives a reset). To resolve in the runtime build, not here. The MCP owes it only `get_plan` + the existing reads the agent uses to assemble context.
- **Auto-entry of quantities** (Apple Health etc.) — spec future; `log_outcome`/`log_progress` stay manual for MVP.
- **Two-way completion sync** (goal ↔ task write-back) — ADR-0005 keeps MVP one-way; no tool.
## 6. Open behavioral items that touch tool phrasing (not tool shape)
- **OQ-COMP-1** — how explicitly the bot names a chronic-miss pattern back to the user. Affects the *phrasing* the LLM wraps around the §3.2 reassessment tools, not the tools themselves. Carried in the behavioral pass.
- **OQ-PSY-1** — upward (offensive) recalibration: detect a floor cleared with room to spare, *offer* to raise it. If adopted post-MVP it implies a promote-want-to-need action that would reuse `create_goal_version`; no new tool anticipated. Deferred.
---
 
## 7. Tool count summary
Ritual writes: 5 (`log_outcome`, `log_progress`, `record_reflection`, `lock_in_plan`, `add_win`).
Reassessment lifecycle: 3 (`set_goal_lifecycle`, `create_goal_version` [scoped], `set_rotation_pointer`).
Ingestion authoring: 4 (`create_chapter`, `create_goal`, `create_goal_version`, `update_goal`).
Shared reads: 5 (`get_full_goal_list`, `get_goals_for_chapter`, `get_goal_detail`, `get_plan`, `get_active_chapter`).
 
`create_goal_version` is shared between the ritual (scoped) and ingestion grants, so the distinct-tool count is **16**. The surface is small because §1 holds: selection, surfacing, budget math, pointer/counter/shared-state computation, and profile resolution are all deterministic Python behind the boundary, not tools.
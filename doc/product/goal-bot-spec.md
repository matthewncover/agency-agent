# Goal Accountability Bot — Spec v0.5 (Draft)
 
> Status: draft. Rounds 1–2 + confirmations folded in. **Structural convergence pass folded in (v0.4 → v0.5):** architecture §9's flagged edits applied (person + Tier-1 → `profile` schema; `owner_profile_id` on goal tables; `task_ref` on one-off `goal_version`; morning-ritual split agent-generic vs. goal-specific); chat-T structural decisions applied (D-17 group-profile supertype, D-18 chapter-scoping); `accumulation` added to the recurrence enum; OQ-16 dissolved. ADR cross-refs: 0012 (group-profile, supersedes 0004), 0013 (chapter-scoping), 0014 (defer agent/app split → three packages). **This pass is structure-only**; the R1/R2 behavioral decisions (psychology/competitive) are a separate convergence pass and are *not* folded in here. Pinning, three-tier memory, and the rotation pointer are **[Decided]**. This doc is about to be split into focused sub-docs (see the meta plan); treat it as the canonical product spec until then.
 
---
 
## 1. Purpose & objectives
 
A single Telegram bot, shared by two people (you and your girlfriend), that helps each of you plan, track, and reflect on personal goals — and over time gets smarter about what actually gets in your way.
 
**Key objectives** (things to orient toward, not hard pass/fail requirements):
 
1. **Maximize likelihood of meeting goals.**
2. **Low friction of use** — using it at all, consistently, beats collecting perfect data.
3. **Fit our specific psychology**, not the generic average person.
**The deeper purpose underneath the objectives:** practice *keeping promises to yourself*. The locked-in plan is a promise; the morning-after reflection surfaces what made promises hard to keep, so you both become more realistic over time. "Misses" are treated as **data, not verdicts** — this matters because both users run hard on themselves, and a nightly report-card dynamic would feed exactly the self-criticism loop we're trying to work against.
 
### The 95% Floor (foundational principle) **[Decided]**
The single most important concept in the system. A **need** goal's minimum bar is defined as:
 
> *Given all the ways you know you tend to betray and sabotage yourself, and the real variance in schedule and life, the bar you are **95% sure** you both **would** do and **could** do.*
 
This is the calibration target everything else serves. A need that keeps getting missed isn't a personal failure — it's evidence the bar was set above the 95% floor, i.e. miscalibrated. That reframing is what makes the carry-over and reassessment behavior (§3) non-punitive by design.
 
---
 
## 2. The two people
 
| | Person A (you) | Person B (girlfriend) |
|---|---|---|
| Enneagram | 3w4 (confident) | likely 8w7 (not confident) |
| MBTI | ENFJ | ENFJ |
| HBDI | untested / unknown | 2-1-1-1 |
| CliftonStrengths (top 5) | Achiever, Developer, Competition, Significance, Analytical | Achiever, Developer, Competition, Learner, Activator |
 
Shared: both high-achieving, both hard on themselves, both ENFJ, shared top strengths Achiever / Developer / Competition. Different time zones.
 
> Design implication: surfacing **recent wins / things already accomplished** is a deliberate counterweight to the shared tendency toward self-criticism. **[OQ-1 — Decided in principle, see §7]** The overlap between the two profiles dominates; we will *not* build two tone engines. Personality is profile context that nudges *framing at the margin*, and the real personalization comes from per-person constraint-learning.
 
Scope note: **no work/career goals** for now, but keep the model open to them. Everything else (health, relationships, personal development, finances, hobbies, etc.) is in scope.
 
---
 
## 3. The daily ritual (morning-only)
 
Everything happens in **one morning touchpoint** per person, sent at that person's chosen local time. No separate evening ritual — that was a deliberate choice to (a) reduce friction and (b) avoid the nightly report-card dynamic.
 
> **Structural split (architecture §9 / ADR-0010 reasoning, ADR-0014 packaging).** The ritual decomposes into a **generic loop** and **goal-specific logic**, and the two must not bleed together in code even though they ship in the same package for MVP (ADR-0014 collapses the standalone `agent`/`app` packages; the *boundary* survives as an internal module line, see meta-plan §3):
> - **Generic loop (agent-runtime concern):** schedule the per-person touchpoint at local time → build context → run the LLM turn → deliver over Telegram → persist the result. Domain-agnostic; knows nothing about needs/wants/quotas.
> - **Goal-specific logic (goal-bot concern):** smart-subset selection, need/want semantics, carry-over, the lighter-day nudge, shared-goal surfacing. Sits behind the capability boundary.
>
> Keeping this line visible in the code is what makes a later extraction of a standalone runtime a lift-out rather than a rewrite (ADR-0014). Everything below describes the goal-specific half unless noted.
 
A morning check-in does two things:
 
**A. Review yesterday — framed as "what shifted," not "did you fail."**
- Shows what was locked in yesterday and what actually happened.
- Asks, optionally, what changed (mood, schedule, motivation, an unexpected obstacle). This reflection is **the real gold** — it's the most perishable data and the main input to pattern-finding and profile updates.
- Emphasis is *not* on what didn't happen. Incomplete items simply carry over.
**B. Plan today.**
- Surfaces a **smart subset** of suggested items for the day (not the whole list).
- Recurring items (e.g. workout-split item for the day, daily step target) appear automatically.
- Schedule-aware: profiles can note that certain days are heavy (e.g. her Tue/Wed are meeting-dense), making some goals harder.
- Frequency goals (e.g. gym 3×/week) are budgeted against days left in the window — "you've got X sessions and Y days left."
> **Rough definition of "smart" (v1 candidate).** The full refinement is still **[OQ-10]**, but here's a concrete starting heuristic so "smart" isn't hand-wavy. The subset = the union of three buckets, then trimmed:
> 1. **Must-show (auto):** every `daily` item, plus today's computed `rotation` item (see §5 — renamed from `cycle` to avoid clashing with *chapter*). These always appear — no judgment call.
> 2. **Due-by-budget:** any `quota` goal where remaining sessions ≥ remaining days in the window (i.e. it *has* to happen today or the week breaks), forced in. Quota goals with slack are offered as candidates, not forced.
> 3. **Candidates:** `oneoff` items with a near/overdue target date, plus anything carried over from yesterday.
> Then **trim for realism:** if the profile marks today as a heavy day, cap the number of *suggested* (non-must-show) items so the plan stays achievable — protecting objective 1 (likelihood) and the promise-keeping goal. The user can always ask for the full list to override the trim.
> Everything here is deterministic except the heavy-day cap, which is where personality/profile judgment enters. This is intentionally simple for MVP; **[OQ-10]** is about whether it stays rule-based or hands more of the selection to the LLM.
> **[OQ-15 — Decided]** The "maybe today's a lighter day" nudge can target **anything that is *not* a need.** Needs are exempt — they're the protected promises. Want-level items (including want-level daily/rotation items in the must-show bucket) remain eligible for the nudge. So a recurring item's exemption is determined by its **level**, not by its recurrence type.
- You can ask to **see the full list** and reshuffle, move items between **needs** and **wants**, or remove them.
- Then you **lock in**. If you say nothing, the AI's suggestion is treated as locked. **[OQ-2 — Decided]** No timer or cutoff. The morning suggestion is **persisted as a provisional plan the moment it's sent**; if you never explicitly lock, then the *next* morning's retrospective simply treats that provisional plan as what was locked. (Implication: the suggestion must be saved up front so an implied lock always has concrete content to reflect against.)
### Needs vs. wants **[Decided]**
Collapsed from a per-day classification into a property of the **goal definition** itself:
 
- A goal's **need definition** is its **minimum bar** — the 95% Floor (§1).
- A goal's **want definition** is its **stretch** — the same goal, aimed higher.
- A goal can carry a need definition **and/or** a want definition. **[Decided: both can be active at once]** — e.g. steps need = 6k *and* want = 10k coexist within a chapter as two concurrently-effective versions (`level='need'`, `level='want'`).
- **Level is fixed until you edit the goal. [Decided]** There's no per-day demotion. If a need is too heavy to sustain, you don't quietly drop it to a want for a day — you **edit/reassess the goal** to re-anchor it to the 95% Floor. This keeps the meaning of "need" honest: a need is a need until you deliberately recalibrate it.
So minimum-bar/stretch and need/want are the *same axis*, not two — the per-day `classification` field is removed entirely.
 
### Carry-over, reassessment & the gentle nudge **[Decided]**
- **Never auto-drop.** Nothing leaves the system without a human deciding.
- **Wide berth: ~1 week** of misses before any nudge fires.
- The behavior splits by goal type:
  - **One-off tasks:** after ~a week of sliding, the bot gently asks whether it's still a **need**, should move to a **want**, or should be **dropped**. (Drop is offered here, but only here, and only with the human choosing it.)
  - **Recurring / non-one-off goals:** dropping makes no sense, so after ~a week of misses the bot instead softly suggests a **reassessment** — re-anchoring the minimum bar to the 95% Floor. The framing is always "the bar may have been set above your floor," never "you failed."
This keeps the meaning of "locked in" intact while routing every chronic miss back to the 95% Floor rather than to self-blame.
 
---
 
## 4. Goal authoring & editing
 
- Goals are authored as **markdown** (likely in Obsidian), each carrying: **minimum bar** (need definition) and/or **stretch** (want definition), **why**, **anticipated obstacles**.
- The markdown is pushed up and run through an **AI ingestion layer** that parses loose, lightly-structured text into **tagged database records** (tagged per person, or as shared).
- The **database is the source of truth**; markdown is a working copy. You can **export to markdown**, edit during a check-in, and push changes back up (AI reconciles the messy text into updates).
**Identity & re-ingest reconciliation [OQ-5 — Decided]:** This is the bed of snakes from round 1; the resolution is to stop inferring identity from content.
- **Identity is conferred by ID, never derived from goal contents.** When the AI exports markdown for editing, it writes the goal's **ID** alongside it. On re-ingest, an item with a known ID = update the existing goal (new version). An item with no ID = a *new* goal — but the AI is wary and surfaces a possible-duplicate warning when text closely matches an existing goal.
- **Changing the minimum bar does NOT create a new goal.** Steps 6k → 8k is the *same* goal, a new version; that evolution is exactly what we want to track. Same ID ⇒ same lineage.
- **"New goal vs. new version" is a human call the AI surfaces, not one it makes silently.** If an ID'd goal's content has changed a lot, the AI asks "version-bump or split into a new goal?" rather than guessing.
- **Grouping is handled by tags, which are orthogonal to identity.** Tags answer "what bucket / domain is this?" (`movement`, `health`, `relationship`), not "is this the same goal?" Two genuinely distinct goals can share a tag; one goal keeps its identity across many versions. Keeping these two concerns separate is what untangles the snakes.
- Goals are **versioned** and history is fully preserved (it'll be small, and seeing how goals evolved is itself valuable).
- There are periodic **check-ins** where goals get adjusted. **[OQ-6 — Decided]** These blocks are called **chapters** (evokes "a new chapter"; she's an author). A chapter is **owned by a profile** (`owner_profile_id`, §6) — an individual person *or* the group/household profile (D-17). Each person has their **own** chapters (own dates + theme); a **group-owned** chapter is the joint-push case (replacing the old `owner_scope='shared'` flag). Default toward aligning/sharing for flexibility, but individual ownership stays possible so differing lives/time zones don't force lockstep.
- **Goals are chapter-scoped [D-18 — Decided].** A goal optionally belongs to one chapter via `goal.chapter_id` (nullable — chapter-less goals are allowed and simply persist across windows untouched). For *chaptered* goals, identity (`gid`) resolves within the chapter; at **rollover** (a new chapter window), carried-forward goals become **new goals scoped to the new chapter** with fresh IDs, and the prior chapter's goals close. "Same goal across chapters" lineage is **not** tracked for MVP — it's a deferred future-analysis problem (and the reason proactive last-chapter hit-rate calibration is post-MVP, not in this loop).
**Out of scope for MVP (future):**
- Inline goal add/edit through the Telegram chat itself.
- Optional mid-day "drive-by" note (capturing obstacle context in the moment). Noted but not pursued now.
- **Leverage the existing `task-tracker` MCP:** separate chats for adding/updating tasks into the task DB, then at chapter-setting time the AI proposes goal candidates drawn from *past goals + open tasks* — blending urgent items with the important-but-not-urgent self-actualization goals. **Candidate set = `personal_tasks WHERE tier IN (2,3) AND owner_id = P`** (owner-scoped; `work_tasks` excluded — no work goals), gathered deterministically by goal-bot via task-tracker's typed read-only client and surfaced to the LLM as a prepared list (ADR-0005, ADR-0007). (Tool already built; integration parked.)
- **Email the full goal list** on request.
---
 
## 5. Goal types — the behavior drivers ⚠️ *needs scrutiny*
 
This is one of the two areas you flagged for extra thought. The behaviors decompose into a few **orthogonal dimensions** rather than one "goal type."
 
> **What [OQ-7] actually was (now Decided):** a pure data-modeling fork. *Option A* — a single `goal_type` enum with bundled values like `daily_workout`, `weekly_gym`, `oneoff_task`; simple but rigid (every new combination needs a new enum value and the behavior is welded together). *Option B* — separate columns for recurrence / completion / ownership / surfacing, where a goal is any sensible **combination** (steps = daily + quantity; gym = quota + binary). We're going **Option B (orthogonal)** — it's already how the schema is written, and the dimension-thinking is what made the model tractable. The cost is that you must validate that combinations make sense (e.g. `oneoff` + `quota` is nonsense), but that's cheap.
 
**Dimension 1 — Recurrence pattern** (drives surfacing & budgeting):
- `oneoff` — a discrete task ("I told her I'd do X"); surfaces until done, maybe has a target date.
- `daily` — appears every day (e.g. step count).
- `rotation` — an ordered sequence of session types (e.g. push → pull → push …) with a **pointer**. **[Redesigned — see callout below]** The pointer is **completion-advanced, not calendar-advanced**.
- `quota` — N times per window (e.g. gym 3×/week). Requires budgeting logic against days remaining in the window.
> **⚠️ Rotation redesign (your catch).** The v0.2 model keyed rotation to `anchor_date + position`, so the right item was a pure function of the calendar. That's wrong: **miss a push day and the calendar model says tomorrow is rest** — but you want tomorrow to *still be push*. Fix: rotation carries a **pointer into the sequence that only advances on completion (or an explicit skip)**. A missed action item keeps the pointer where it is, so it re-surfaces. *Rest/spacer* items advance automatically with a passing day (you don't "do" rest), so the sequence still flows push → (rest auto-clears) → pull. This means rotation needs stored pointer state, not just a formula — a real schema consequence (see §6 `goal_state`).
>
> Deeper structure worth noting (probably post-MVP): the workout case is really **progression** (*what's* the next session — the pointer) × **cadence** (*whether* today is a session day — spacing/rest gaps, which is quota-like). For MVP, completion-advanced rotation with auto-clearing rest items covers it; separating progression from cadence is a future refinement.
 
**Category calls — [Decided, chat-T].** The brainstorm below is now resolved: `interval`, `fixed_schedule`, `accumulation`, and the `paused` lifecycle state are **IN for MVP** (the goal-markdown template exercises all four); `scale`/rating stays **OUT** until a goal needs it. **Jade's gym = `quota`** (3× flexible/week), not `fixed_schedule`.
- **`interval` recurrence — IN.** Every-N-days *measured from last completion* (water plants every 3 days; pushups every 4). Distinct from `quota` (N-per-fixed-window) because the clock resets on completion (`goal_state.last_completed_at`).
- **`fixed_schedule` recurrence — IN.** Specific weekdays/dates (Mon/Wed/Fri; the 1st). Distinct from `quota` — the days aren't flexible. *Must name its days* to disambiguate from quota at ingest.
- **`accumulation` recurrence — IN.** Progress toward a chapter-level target (4h on the painting; read 12 books; save $5,000). Sums logged progress toward one total; distinct from `quota` (which counts discrete sessions). Inherently chapter-scoped (fits D-18).
- **`scale`/rating completion — OUT (future).** Subjective 1–5 (rate sleep quality, diet adherence).
- **`paused` lifecycle state — IN.** A goal intentionally dormant for a stretch (injured → pause the gym goal) without being dropped or archived. Sits alongside active/archived; the soft on-ramp for genuine-abandonment reassessment.
- **Ownership:** no new *type* needed — ownership is now `owner_profile_id` → person-or-group (D-17), so "both must do it" is either two individual goals or one group-owned goal; the old `individual`/`shared` enum is gone.
**Dimension 2 — Completion type** (drives what "done" means):
- `binary` — did / didn't.
- `quantity` — hit a number (steps: 8,000). **[OQ-8 — Decided]** The **goal's owner enters the number the following morning** (during the retrospective). Future: pull automatically (e.g. Apple Health API). On "partial": a partial is **informational only for quantity goals** — if you logged 4,000 of an 8,000 step goal, that's recorded as `partial` with the actual number for pattern-mining, but it does **not** tick a quota counter. Quota counting is per-session binary (see below), so "does a partial count toward quota" resolves to *no*.
- `duration` — time-based. (May collapse into quantity.)
**Dimension 3 — Ownership:** *(now expressed via `owner_profile_id`, not an `individual`/`shared` enum — D-17 / ADR-0012)*
- **Individual** — owned by a person profile.
- **Shared** — owned by the **group/household profile** (e.g. the couple). This replaces the old `owner_scope='shared'` flag: a shared goal is just an ordinary goal whose owner happens to be a group, inheriting all recurrence/completion semantics. **[OQ-9 — Decided]** **Either** member completing it marks it done (if it genuinely needed *both*, you'd model it as two individual goals instead). Group goals are **not auto-suggested** into anyone's daily plan; instead they fan out into a **separate response block** in each member's morning interaction (alongside the individual plan, not interleaved), and either member can choose to take one on for the day. Completion is shared state: if she completes it, it reads as done for both. *(Cross-timezone nuance handled in §8.)*
**Dimension 4 — Surfacing behavior:**
- `auto` — always appears (recurring items).
- `suggested` — AI decides whether to float it today.
- `on-demand` — only shows when you ask for the full list.
> The "smart subset" in the morning is a function over these dimensions + profile (schedule heaviness, patterns, budgets). **[OQ-10 — Decided for MVP]** Use the explicit 3-bucket heuristic in §3 (must-show / due-by-budget / one-off candidates, trimmed for realism), and always **offer to surface the full list** for the person to decide. *Future:* this dovetails with the `task-tracker` MCP — each task tier keeps items in approximate rank order, and the subset would pull from the top of one or more tiers by rank. For MVP the AI just takes a stab with the heuristic + offers the full list.
 
---
 
## 6. Data model — Postgres first draft ⚠️ *needs scrutiny*
 
The second area you flagged. This is a sketch to react to, not final DDL. Key decision baked in: **goal identity is separate from goal content**, and content is **version-effective-dated**, so a daily plan can pin the exact version that was true when you locked in.
 
> **Schema ownership (post-structural-pass).** Tables are split across packages/schemas (architecture §2–§3, ADRs 0004/0011/0012): the **`profile`** schema owns identity (`profile`, `person`, `group_profile`, `group_member`) and the **Tier-1 authored profile** (`profile_doc`); **`goal-bot`** owns everything goal-domain and the Tier-2/3 goal memory (`insight`, `friction_log`, `what_shifted`). Cross-schema access is via published ports, never raw cross-schema SQL (ADR-0007). Annotations below mark each table's owner.
>
> **Person-only constraint (application-enforced).** Every `person_id` FK below points at the `profile` supertype but must resolve to a **person** profile (`kind='person'`), never a group — `daily_plan`, `friction_log`, `insight`, `profile_doc` are per-person only. Groups own goals and chapters; they do **not** get daily plans, friction logs, insights, or authored profiles. Postgres can't express "FK to a subtype" without a redundant `kind` column, so this is a **check-at-write** in the application layer, not a DB constraint. (Group goals reach a member via fan-out surfacing into that member's own `daily_plan` — §5/§8.)
 
```
-- ============ profile schema (package: `profile`) ====================
-- Identity is a shared agency-agent primitive. `profile` is the supertype
-- (one id space) so a single `owner_profile_id` FK can point at either an
-- individual or a group — no 'shared'/null special-case. [D-17 / ADR-0012]
 
profile                 -- IDENTITY SUPERTYPE (shared id space)
  id              pk
  kind            enum('person','group')
  created_at
 
person                  -- subtype of profile (shared-PK pattern)
  profile_id      pk, fk -> profile.id   -- IS the identity; not a separate id
  display_name
  timezone
  morning_prompt_local_time
  -- channel-agnostic: the telegram_user_id -> person map is a RUNTIME concern
  --   (agent module), NOT a profile column. [ADR-0004, unchanged by ADR-0014]
 
group_profile           -- subtype of profile: a couple / household
  profile_id      pk, fk -> profile.id
  label           text                   -- e.g. 'Matthew & Jade'
 
group_member            -- membership: which persons belong to a group
  group_profile_id  fk -> group_profile.profile_id
  member_person_id  fk -> person.profile_id
  pk (group_profile_id, member_person_id)
  -- members are persons only; no nested groups for MVP.
 
profile_doc             -- TIER 1: authored, human-owned, trusted (per-person)
  id              pk
  person_id       fk -> person.profile_id
  section         text          -- 'identity','priorities','schedule','personality','patterns'
  content         text          -- human-edited prose
  updated_at
  -- only humans (or human-approved AI proposals) write here. [ADR-0011]
 
-- ============ goal-bot schema (package: `goal-bot`) ==================
-- TIER 2 observations live below as friction_log + the what_shifted field
--   on daily_plan_item (append-only events). TIER 3 = `insight`.
--   All three stay domain-local in goal-bot. [ADR-0011]
 
insight                 -- TIER 3: AI-maintained, advisory, compressed
  id              pk
  person_id       fk -> person.profile_id
  content         text          -- "patterns I'm noticing" digest entry
  status          enum('active','proposed_for_profile','graduated','dismissed')
  derived_from    jsonb         -- pointers to the Tier-2 events behind it
  created_at, updated_at
  -- auto-written by AI; graduates into profile_doc ONLY on human approval
-- ---------------------------------------------------------------------
 
chapter                 -- the goal-setting block (was "cycle") [Decided §4]
  id              pk
  label                          -- the chapter's theme/name
  owner_profile_id  fk -> profile.id   -- person OR group profile [D-17]
                                       --   (replaces owner_scope/person_id)
  start_date
  end_date
 
goal                    -- stable identity (identity = id, never content)
  id              pk
  owner_profile_id  fk -> profile.id   -- person OR group profile [D-17]
                                       --   (replaces owner_scope/person_id)
  chapter_id      fk -> chapter (nullable)   -- chapter-scoped when set; null = persists
                                             --   across windows untouched [D-18]
  title           text          -- human label; NOT used to infer identity
  created_at
  archived_at     (nullable)
 
tag                     -- grouping, orthogonal to identity [Decided §4]
  id              pk
  name            text  unique   -- e.g. 'movement','health','relationship'
 
goal_tag                -- many-to-many
  goal_id         fk -> goal
  tag_id          fk -> tag
 
goal_version            -- mutable content, versioned + effective-dated
  id              pk
  goal_id         fk -> goal
  version_no      int
  level           enum('need','want')  -- which definition this version is
  definition      text          -- the bar text; "minimum bar" if need, "stretch" if want
  why             text
  recurrence_type enum('oneoff','daily','rotation','quota','interval','fixed_schedule','accumulation')
  recurrence_config jsonb       -- see examples below
  completion_type enum('binary','quantity','duration')
  target_quantity numeric (nullable)
  quantity_unit   text    (nullable)
  task_ref_source enum('personal','work') (nullable)  -- one-off goals only [ADR-0005]
  task_ref_id     int (nullable)                       -- FK-by-reference into task-tracker;
                                                       --   recurring goals never carry this.
                                                       --   Invariant (APPLICATION-ENFORCED, not a DB
                                                       --   constraint — separate schemas, no cross-
                                                       --   schema FK): referenced task's owner must
                                                       --   match the goal's owner. Checked at write
                                                       --   via the typed task client (ADR-0005/0007).
  effective_from  timestamptz
  effective_to    timestamptz (null = current)
  lifecycle       enum('active','paused','archived')  -- 'paused' = dormant, not dropped (§5)
  created_at
  -- [Decided §3] need/want lives HERE via `level`, not on the daily item.
  --   A goal with both a need-form and a want-form has TWO concurrently-
  --   effective versions (level='need' and level='want'); both are valid.
 
goal_state              -- rotation pointer + other per-goal mutable state (§5)
  goal_id         fk -> goal   (pk)
  rotation_index  int          -- current position in the rotation sequence;
                               --   advances on completion/skip, NOT on the calendar
  last_completed_at timestamptz (nullable)  -- also supports `interval` recurrence
  updated_at
 
anticipated_obstacle    -- the obstacles listed at authoring time
  id              pk
  goal_version_id fk -> goal_version
  text
 
daily_plan              -- one per PERSON per day (groups don't get plans;
                        --   group goals fan out into each member's plan — §5/§8)
  id              pk
  person_id       fk -> person.profile_id
  plan_date       date          -- the "day" runs to the next 6a local boundary [Decided §8]
  locked_in_at    timestamptz (nullable)
  lock_was_explicit boolean
  created_at
 
daily_plan_item
  id              pk
  daily_plan_id   fk -> daily_plan
  goal_id         fk -> goal
  goal_version_id fk -> goal_version   -- pinned to version at lock time;
                                       --   the version's `level` already says need/want,
                                       --   so a separate classification field is dropped
  status          enum('planned','done','partial','not_done','carried_over')
  quantity_actual numeric (nullable)
  what_shifted    text (nullable)      -- the morning-after reflection
  carry_over_count int default 0       -- drives the ~1-week reassessment nudge [§3]
  created_at, updated_at
 
friction_log            -- OBSERVED obstacles; the pattern-mining gold
  id              pk
  person_id       fk -> person.profile_id
  goal_id         fk -> goal (nullable)
  daily_plan_item_id fk (nullable)
  text
  logged_for_date date
  created_at
 
win_log                 -- [OQ-13 — Decided] keep it. Wins can be added manually
  id              pk    --   any time, AND the system derives wins from done items.
  person_id       fk -> person.profile_id
  goal_id         fk (nullable)
  source          enum('manual','derived')
  text
  created_at
```
 
**`recurrence_config` (jsonb) examples:**
```jsonc
// daily fixed
{ "type": "daily" }
 
// rotation — sequence + which items are "spacers" that auto-advance.
//   Live pointer is in goal_state.rotation_index, NOT here (completion-advanced).
{ "type": "rotation",
  "sequence": ["push","rest","pull","rest"],
  "auto_advance_values": ["rest"] }
 
// quota (3x per flexible week)
{ "type": "quota", "count": 3, "window": "week", "week_start": "monday" }
 
// interval — every N days measured from last completion (uses goal_state.last_completed_at)
{ "type": "interval", "every_days": 3 }
 
// fixed_schedule — specific weekdays
{ "type": "fixed_schedule", "weekdays": ["mon","wed","fri"] }
 
// accumulation — cumulative quantity toward a chapter target (sums logged progress)
{ "type": "accumulation", "target": 4, "unit": "hours", "window": "chapter" }
 
// one-off
{ "type": "oneoff", "target_date": "2026-07-01" }
```
 
**[OQ-14 — Decided: pin].** Each day's record remembers *the version of the goal you actually committed to that day*, even if the goal changes later. Concretely:
 
- **June 1:** your Steps goal's need bar is **6,000** (call it version v1). You lock in June 1; that `daily_plan_item` pins **v1**.
- **June 15:** you reassess and raise the bar to **8,000** (version v2; v1's `effective_to` closes).
- **June 20 morning:** the prompt reads the **current** version → shows **8,000**.
- **Looking back at June 1:** it still shows you committed to **6,000**, because the item pinned v1. You did *not* retroactively "fail to hit 8,000" on a day when 8,000 didn't exist yet.
**Confirmed:** pin. Hitting 6k on June 1 stays a success even after the bar later moves to 8k — raising the bar must not retroactively invalidate past wins. (Without pinning, old records float to the newest bar and the history lies.)
 
### 6a. What's load-bearing vs. cheap to change (you asked about iteration risk)
Since we'll iterate, here's where to think hard *now* vs. defer — i.e. what's expensive to migrate later:
 
**Hard to change later (decide carefully now):**
- **The `goal` ↔ `goal_version` identity/versioning split**, and **pinning `goal_version_id` on `daily_plan_item`.** Retrofitting versioning onto a flat goals table after you have history is painful. This is the spine.
- **Ownership via `owner_profile_id` → the `profile` supertype** on goals and chapters. Ownership semantics leak everywhere; changing them later touches surfacing, completion, and shared-state logic. The supertype (person/group share one id space) is the structural choice that makes "shared" and future family/household expansion ordinary ownership rather than a special-case — chosen now precisely because retrofitting a group identity onto an `owner_scope='shared'` flag after there's history is the painful path (D-17 / ADR-0012).
- **The three-tier memory boundary** (Tier 1 authored vs. Tier 3 inferred). If you start letting AI write into the authored profile, clawing that trust boundary back later is hard.
- **The day-boundary definition** (6a local). Carry-over, streaks, and "what happened yesterday" all depend on it; changing it reinterprets historical rows.
**Cheap to change later (don't over-think now):**
- **Enum *values*** — adding a recurrence type, completion type, or lifecycle state is a one-line migration. So the "did we miss a category" brainstorm in §5 is low-risk to get wrong.
- **`recurrence_config` jsonb shape** — it's schemaless by design; evolve per type freely.
- **Adding tables** (e.g. a future `automation_source` for Apple Health) — additive, low-risk.
- **Surfacing heuristic / the smart-subset logic** — it's app logic, not schema; rewrite anytime.
Rule of thumb: **identity, ownership, versioning, and trust boundaries are structural; everything behavioral or enumerable is soft.** Spend the scrutiny budget on the first list.
 
---
 
## 7. Personality, profile & memory architecture **[mostly Decided; one piece Proposed]**
 
### 7a. Personality → tone **[Decided in principle]**
**Decision: no two-tone engine.** The two profiles overlap heavily (both ENFJ; shared Achiever / Developer / Competition; both hard on themselves). Having the bot speak in two visibly different voices in one shared chat would be more gimmick than value. Personality data is stored as **profile prose** (plus a couple of light structured fields for the raw assessment results), read by the LLM, and allowed to nudge **framing at the margin** — not to branch behavior.
 
Where the profiles *do* meaningfully diverge, and how that shows up as framing (same content, different doorknob):
- **Activator (her) vs. Analytical (you).** She's wired to start and move; you're wired to want the data/proof. A nudge to her can be action-framed ("want to just lock it and go?"); the same nudge to you can be evidence-framed ("this slid 4 of 5 days — want to look at why?").
- **Enneagram 8w7 (her) vs. 3w4 (you).** Her 8 prizes autonomy and responds to being *given control / challenged* rather than told what to do. Your 3w4 responds to achievement framing, but the 4 wing means generic "crush it" cheerleading rings hollow — wins land better when tied to meaning, not just a scoreboard.
- **Significance (you) vs. Learner/Activator (her).** For you, surfacing wins works best when connected to "this is part of becoming who you're trying to be"; for her, wins read as fuel to keep moving.
### 7b. The three-tier memory model **[Decided]**
The round-1 framing lumped several different things into "profile." They have **different trust levels and different lifespans**, so they shouldn't be one doc. Proposed split into three tiers:
 
**Tier 1 — Authored profile (human-owned, trusted, slow-moving).**
One curated doc per person (sectioned: identity & values, stable priorities, schedule structure, personality results, known self-sabotage patterns). **Only humans edit it** — the AI may *propose* additions but never silently writes here. This is the authoritative "who this person is," and it's the only memory the morning bot treats as ground truth. Because it's small and curated, the LLM can hold it in context every morning without trouble.
 
**Tier 2 — Observations (append-only events, raw).**
The per-day EOD reflections / "what shifted" notes and the friction log. These are **timestamped events, not profile statements** — so, to your question, **yes, EOD reflections live separately from the core profile docs.** They're evidence, not conclusions. Append-only is fine *here* precisely because nothing reads the whole log live; it's raw material for periodic mining.
 
**Tier 3 — Insights digest (AI-maintained, advisory, compressed).**
Periodically (e.g. weekly, or at chapter check-ins), the AI reads Tier 2 and maintains a short, clearly-labeled "patterns I'm noticing" digest per person ("workouts slip the day after poor sleep"; "evening goals fail when meetings run past 6"). This is where **AI summaries earn their keep** — they're a *compression layer* so the model isn't re-reading hundreds of raw events every morning and isn't re-deriving patterns daily. Crucially, the digest is **advisory and subordinate**: it never mutates Tier 1. When a pattern looks solid, the AI *proposes* "want me to add this to your profile?" and on your approval it **graduates** into Tier 1.
 
This directly answers your three worries:
- *Append-only log + limited context + conflicts* → the bot never reads the raw log live; it works from curated Tier 1 + compressed Tier 3. Conflicts resolve cleanly because Tier 1 is authoritative and Tier 3 is explicitly "just hypotheses."
- *Where AI summaries help* → as the Tier-3 compression/working-memory layer and as the proposal mechanism into Tier 1.
- *Should EOD reflections be separate in the DB* → yes; they're Tier 2 events.
**EOD-inference application rule [resolves the OQ-11 sub-question]:** inferences are **auto-applied only to the advisory Tier 3 digest**, and **human-approved to graduate into the trusted Tier 1 profile.** Nothing the AI infers ever silently rewrites the authoritative doc.
 
> This also keeps a healthy boundary: the system's authoritative model of each of you stays *yours to author*, with the AI as a pattern-spotter that proposes, not a ghostwriter that overwrites.
 
---
 
## 8. Identity, time zones, delivery **[Decided]**
 
- The bot identifies who's speaking via **Telegram user ID** (hard-coded: this id = you, this id = girlfriend).
- Each goal/record is **tagged per person** (or shared).
- Morning prompts fire at **6:00a each person's local time** — 6a ET for her, 6a PT for you.
- **The "day" ends at that same 6:00a local boundary.** Yesterday runs until 6a today; carry-over and "what happened yesterday" are evaluated against that line.
- **Timezones are editable any time** (you both travel). *Future:* update timezone automatically by some means.
- **Shared (group-owned) goals across two zones:** completion is tracked by timestamp and is shared state — whichever member completes it first marks it done for both. Because group goals are availability-style (not auto-suggested daily), the per-person 6a boundary matters less for them; a group goal simply reads as done once either member completes it. **[OQ-16 — Dissolved by D-17 / ADR-0012]** The reset-vs-persist question disappears once shared goals are *ordinary goals owned by a group profile*: a group goal follows the **normal recurrence semantics of its `recurrence_type`**, exactly like an individual goal. A daily group goal resets daily; an accumulation group goal persists to its chapter target; a one-off persists until done. No special shared-goal cadence rule is needed.
---
 
## 9. MVP scope (proposed cut line)
 
**In:**
- One shared Telegram bot; per-person tagging via Telegram ID; 6a-local mornings + day boundary.
- Postgres source of truth, versioned goals with history; identity by ID; tags for grouping.
- Three-tier memory: authored profile (Tier 1) + observations (Tier 2) + AI insight digest (Tier 3); inferences auto-apply to Tier 3 only, human-approved into Tier 1.
- Chapters (goal-setting blocks), owned by a person or the group profile; goals are chapter-scoped (nullable `chapter_id`), rollover creates fresh goals, cross-chapter lineage deferred.
- Identity/ownership via the `profile` supertype (person + group share one id space); shared goals are group-owned, not a special `owner_scope='shared'` flag.
- Markdown authoring → AI ingestion (ID-based reconciliation) → tagged DB records.
- Per-person morning prompt: review-yesterday ("what shifted") + plan-today; provisional plan persisted on send so implied lock has content.
- Smart subset (3-bucket heuristic) + offer full list; reshuffle; need/want as a goal-definition property (both levels can coexist); lock-in (explicit or implied).
- Recurrence types: daily, rotation (**completion-advanced**), quota, one-off, **interval, fixed_schedule, accumulation** (all IN per chat-T); **`paused`** lifecycle state IN. (`scale`/rating out until needed.)
- Carry-over with ~1-week berth → one-offs get a drop/keep nudge, recurring goals get a 95%-Floor reassessment; never auto-drop. Lighter-day nudge targets non-needs only.
- Group-owned (shared) goals: either member completes; separate response block; not auto-suggested; follow normal recurrence semantics (OQ-16 dissolved).
- quantity entered by owner next morning; partials informational, don't tick quota.
- friction_log capture; win_log (manual + derived).
**Future (parked):**
- Inline goal add/edit in chat.
- Mid-day drive-by note.
- `task-tracker` MCP integration: chapter-setting suggestions from past goals + open tasks; tier-rank pull for the smart subset.
- Auto timezone updates; Apple Health (or similar) auto-entry of quantities.
- Email the full goal list.
- Progression-vs-cadence separation for workouts; scale/rating completion.
- Richer personality-driven tone tuning.
---
 
## 10. Open questions — consolidated
 
**Resolved (rounds 1–2):**
- **[OQ-1]** ✅ No two-tone engine; profile prose + light structured fields; framing-at-the-margin.
- **[OQ-2]** ✅ Implied lock = provisional plan persisted on send; next morning treats it as locked.
- **[OQ-3]** ✅ Need/want = goal-definition property (min bar = need, stretch = want); both levels can coexist; level fixed until you edit/reassess the goal.
- **[OQ-4]** ✅ Never auto-drop; ~1-week berth; one-offs → drop/keep, recurring → 95%-Floor reassessment.
- **[OQ-5]** ✅ Identity = ID; min-bar change = new version; tags for grouping; new-vs-version surfaced to human; duplicate-warn on no-ID adds.
- **[OQ-6]** ✅ Block = **chapter**; per-person, can be shared; default toward sharing.
- **[OQ-7]** ✅ Orthogonal attributes (Option B), not a single bundled enum.
- **[OQ-8]** ✅ Owner enters quantity next morning (future: auto); partials informational, don't tick quota.
- **[OQ-9]** ✅ Either completes a shared goal; separate response block; not auto-suggested.
- **[OQ-10]** ✅ MVP = 3-bucket heuristic + offer full list; tier-rank pull is future.
- **[OQ-12]** ✅ 6a-local mornings *and* day boundary; tz editable; future auto.
- **[OQ-13]** ✅ Keep `win_log`; manual entries + derived from done items.
- **[OQ-15]** ✅ Lighter-day nudge targets non-needs only; exemption by level, not recurrence.
- **[OQ-11]** ✅ Three-tier memory (authored / observations / AI insight digest); inferences auto-apply to Tier 3, human-approved into Tier 1.
- **[OQ-14]** ✅ Pin `goal_version_id` on `daily_plan_item`; past wins survive later bar changes.
- **Rotation redesign** ✅ Completion-advanced pointer (`goal_state`); rest items auto-clear.
**Resolved (structural pass):**
- **§5 category calls** ✅ `interval`, `fixed_schedule`, `accumulation`, `paused` are **IN** for MVP; `scale`/rating out. **Jade's gym = `quota`.** (chat-T)
- **[OQ-16]** ✅ **Dissolved** by D-17 — shared goals are group-profile-owned and follow normal recurrence semantics; no special reset-vs-persist rule. (ADR-0012)
- **[D-17]** ✅ Group/household profile owns shared goals via the `profile` supertype; `owner_scope`/null special-case removed from `goal` and `chapter`. (ADR-0012, supersedes ADR-0004)
- **[D-18]** ✅ Goals are chapter-scoped (`goal.chapter_id`, nullable); rollover creates fresh goals; cross-chapter lineage deferred. (ADR-0013)
- **Architecture §9 edits** ✅ person + Tier-1 → `profile` schema; `owner_profile_id` on goal tables; `task_ref` on one-off `goal_version`; morning-ritual generic/goal-specific split; candidates = owner-scoped `personal_tasks` tier 2–3.
- **Packaging** ✅ Three MVP packages (`profile`, `task-tracker`, `goal-bot`); standalone `agent`/`app` split deferred, boundary kept as an in-code module line. (ADR-0014)
**Newly open / deferred (carry forward):**
- **[D-9 — deferred, post-MVP]** Proactive last-chapter hit-rate at bar-setting — needs cross-chapter lineage that D-18 defers. Not assumed anywhere in the MVP loop.
- **[OQ-PSY-1 — deferred, post-MVP]** Upward (offensive) recalibration trigger. *(behavioral pass)*
- **[OQ-COMP-1 — open]** How explicitly the bot names a chronic-miss pattern. *(behavioral pass)*
- **[NULL-TOLERANCE — flag for behavioral pass]** Candidate **design invariant** to formalize: *non-entry is never evidence against the person.* These are busy people; the system must be cool with nulls. Nothing punitive may key off a missing entry, and an unanswered touchpoint is null/neutral, not a miss. Worth writing down as a named principle (sibling to autonomy-supportive phrasing) so a future "engagement" feature can't reintroduce report-card mechanics through the back door. *(behavioral pass)*
- **[ENGAGEMENT-NOT-FAILURE — flag for behavioral pass]** The ~1-week reassessment counter must key off **engagement, not logged failure.** A day the morning touchpoint went unanswered is null/neutral and does **not** advance the counter; the counter only considers days the person showed up and the item still didn't move. Explicitly **no "log your miss" step** — making someone type "I failed" is both friction and the self-criticism ritual the system is built against. (Implication: the carry-over/reassessment logic distinguishes engaged-but-unmoved from never-touched, even though the schema doesn't currently separate them — a behavioral rule over the same `daily_plan_item` rows, not a schema change.) *(behavioral pass)*
- **Workstreams to spin out:** minimum MCP tool set; goal-markdown ingestion template (done — `goal-markdown.md`); VPS move + task-tracker consolidation decision; psychology + competitive research (done — R1/R2 folded in the behavioral pass, not here).
# Goal-Markdown — Authoring Template & Ingestion Contract
 
> **Doc:** `doc/templates/goal-markdown.md` · **v0.7** · status: Phase-2 (chat T) output
> **Role:** Defines (a) the markdown you write goals in (Obsidian), and (b) the contract the *separate* ingestion chat follows to turn that markdown into structured DB records per spec §6. Ingestion runs in its own Claude chat, **not** the Telegram bot. This doc does not build the runtime.
> **v0.6 → v0.7:** **chapter preamble + per-owner docs** (migration 0006). Optional free-prose preamble under the window header — theme, this-season focus, deliberately-parked domains — stored verbatim on `chapter.preamble` and injected into the morning prompt (parked domains are chosen priorities; the bot never nudges toward them). Because chapters are per-profile (windows, themes, and parked lists differ per person), **one doc per owner** (yours, hers, the couple's) is now the recommended layout; the `### Name` ownership headings are unchanged, so a combined doc still ingests.
> **v0.5 → v0.6:** **rotation groups** (ADR-0016): goals sharing one alternating rhythm (pushups / pull-ups) stay separate goals and get a `rotate:` line naming the shared sequence (§2.0, §3.5). The §3.5 "two independent 4-day clocks" artifact is retired — local testing showed the drift is not acceptable (both surfaced the same day).
> **v0.4 → v0.5:** unlabeled one-offs default to **`level=need`** (§2.0, §3.3, §4) — a bare one-off is a committed floor, not a stretch; an explicit `need:`/`want:` label still wins.
> **v0.3 → v0.4:** pushups resolved (`quantity` ⇒ split into two goals). `accumulation` added to the recurrence enum (4h painting). **Goals are chapter-scoped** — rollover creates fresh goals in the new chapter (§5.6); cross-chapter lineage deferred. Tag starter-set + lightweight stance recorded. Group-profile model for shared goals noted as an architecture decision (dissolves OQ-16).
> **v0.2 → v0.3:** reverted to spec §6's **two-version** model (need + want are separate `goal_version` rows) — keeps level on the pinned version; `why`/`obstacles` written to all active versions on ingest.
> **v0.1 → v0.2:** `if_then`/coping parsing dropped (obstacles stored verbatim); `min:`/`stretch:` aliases dropped (need/want only); disappeared goals auto-archive (reversible); conventions hoisted to top; recurrence quick-reference + rotation example added.
 
---
 
## 1. Design principles (the friction ratchet)
 
1. **You type the bars and the why. Nothing else is mandatory.** Recurrence, completion type, tags, ownership, chapter, level are all inferred or confirmed by ingestion, never hand-filled.
2. **Cadence rides inside the text you'd write anyway.** "gym **3×/week**", "pushups **every 4 days**", a daily step number — recurrence is parsed from natural phrasing, not entered as a field.
3. **`why` is required and foregrounded.** It feeds win-surfacing and intrinsic-motivation framing (psych D-7). It sits directly under the bars.
4. **Friction only ever decreases.** Moving a field TYPED → CONFIRMED → INFERRED is always allowed; adding a required field is a regression.
5. **Identity is conferred by ID, never derived from content** (spec OQ-5). You don't manage IDs; ingestion writes them back as invisible comments. This is the deterministic spine that makes re-ingestion reliable — content-based re-identification is the failure mode this avoids.
**Definitions.** A **bar** is the target for one level: the **need bar** is the minimum (95% floor), the **want bar** is the stretch. A goal carries one or two bars. A bar = the `definition` text (+ its number/cadence) for that level.
 
---
 
## 2. The template
 
### 2.0 Conventions (read once)
 
- **Ownership** comes from the section heading: `### Jade` / `### Matthew` → individual, tagged to that person. `### Couple` → `owner_scope=shared`.
- **Level** comes from the bar label: `need:` and/or `want:`. Both present = one goal with two bars. Drop the old `##### Needs` / `##### Wants` section headers — they can't express a both-bars goal; if present they're treated as cosmetic. **An item with no label at all defaults to `need`** — a bare commitment is a floor, not a stretch. An explicit label always wins (a stretch one-off is possible by writing `want:` on it).
- **A heading with discrete sub-items and no `need:`/`want:` line** is read as **N separate one-off goals** sharing the one `why` and a common tag (see §3.3). Ingestion confirms the split; each exploded one-off defaults to `level=need` (above).
- **Cadence is parsed from natural phrasing.** Override only when you know it'll guess wrong:
  - `cadence: quota 3x/week` · `cadence: fixed Mon/Wed/Fri` · `cadence: interval 4d` · `cadence: rotation [upper, lower, rest]`
  - **`fixed_schedule` must name the days** (weekdays, or month dates) — that's what distinguishes it from `quota`.
  - `cadence: accumulation 4h/chapter` — cumulative target over the chapter (sums logged progress; done at target).
- Other optional inline overrides: `completion: binary` · `paused` (dormant, not dropped) · `target: 2026-07-01` (one-off due date).
- **Rotation group (ADR-0016)** — goals that share one alternating rhythm keep their own blocks (own bars, own logging) plus ONE `rotate:` line anywhere in the section naming the cycle: `rotate: [pushups, rest, pull-ups, rest]`. Entries name goal titles (resolved to `gid`s at ingest) or `rest` (consumes one calendar day). Ingestion creates/updates the group; a goal in a group is scheduled *only* by the group. At rollover the group is re-created against the new chapter's fresh `gid`s (§5.5).
### 2.1 Shape
 
```markdown
6/15 - 7/20            ← chapter window (file header). Optional theme: `6/15 - 7/20 — "Reset"`
 
<optional chapter preamble — free prose before the first `###` heading:
this season's focus, what quietly outranks what, and what's deliberately
parked. Stored verbatim on the chapter; the bot treats parked domains as
chosen, never as slippage. One doc per owner — windows and preambles are
per-person (the couple doc carries the shared chapter's own preamble).>
 
### Matthew
 
- <goal title, cadence phrased naturally if recurring>
  - need: <minimum bar>      ← need-level target. The 95% floor.
  - want: <stretch bar>      ← want-level target. Optional reach.
  - why: <required>          ← load-bearing; one line or several
  - obstacles:               ← optional; stored verbatim, one row per bullet
    - <obstacle, write it however you want>
    - <obstacle>
```
 
One block = one goal = one ID, whatever the bar count. `need:` only → need-only goal; `want:` only → want-only goal; both → one goal carrying both bars. All three read identically clean.
 
### 2.2 Recurrence quick-reference
 
| Type | Means | Example |
|---|---|---|
| `oneoff` | a discrete task, optional due date | renew passport |
| `daily` | every day | step goal |
| `quota` | N per window, **flexible** days | gym 3×/week |
| `fixed_schedule` | **specific named** days | Mon/Wed/Fri; the 1st |
| `interval` | every N days **from last completion** | pushups every 4 days; water plants every 3 |
| `rotation` | ordered session sequence, **completion-advanced** pointer | a strict A/B/C split done in order |
| `accumulation` | cumulative quantity toward a **chapter** target | spend 4h on the painting; read 12 books |
 
**Rotation, concretely** (none of your current goals are rotations — Jade's gym is `quota`): you follow `[upper, lower, rest]` in order. Do *upper* → pointer moves to *lower*. **Miss *lower* → the pointer holds**, so *lower* re-surfaces tomorrow (the calendar doesn't skip you ahead). *Rest*/spacer items **auto-advance** with a passing day (you don't "do" rest). Contrast `quota` (any 3 days) and `fixed_schedule` (named days).
 
---
 
## 3. Worked examples (your goals, mapped)
 
### 3.1 Two bars — daily, quantity
 
```markdown
### Matthew
 
- step goal
  - need: 5,000 steps
  - want: 7,000 steps
  - why: vitamin D for mood and sleep; walking relaxes my nervous system and clears post-meal brain fog; reminds me I don't always need to be productive.
  - obstacles:
    - waking late and rushed - shift bedtime earlier
    - gassed after work - walking isn't strenuous, it's the winddown
    - "got steps yesterday, I'm good" - parents walk 2x mine, daily
```
 
→ **1 goal** (`owner=Matthew`) → **2 versions**: `need` (`target=5000`) and `want` (`target=7000`), both `recurrence=daily`, `completion=quantity`, `unit=steps`. `why` + the 3 verbatim obstacle rows written to **both** versions on ingest (§4 note).
 
### 3.2 One bar (need-only) — quota, multi-component session
 
```markdown
### Jade
 
- go to the gym 3x a week
  - need: 15m cardio + 20m lifting + 10m stretching, 3x per week
  - want: 4x per week
  - why: fast way to re-prove I can do hard things; always feel good after; hip weakness from not lifting will cascade to knees and make future-kids harder.
  - obstacles:
    - housework - 10m MadFit full-body video
    - Matthew visiting - gym together or leave his ass behind
    - tired/unmotivated - future kids; going is an act of self-love
```
 
→ 1 goal → 2 versions: `need` (quota count 3) and `want` (quota count 4), both window=week, `completion=binary` (the three components define "the session"; numbers live in `definition` text). Ingestion confirms quota-vs-fixed by default; for this goal the answer is **quota**.
 
### 3.3 A bucket of one-offs — explode-and-confirm
 
```markdown
### Matthew
 
- close the loose ends    ← not one goal; a cluster sharing one why
  - why: little things poking my brain; closing them removes ankle-weights that are sludge on willpower, not muscle.
  - Renew passport
  - Re-register TSA precheck
  - Register Bronco in CA
  - Cancel boxing membership
  - Get money back from Brian Lee
  - Cancel Slovenia plans
```
 
→ **N one-off goals** (`recurrence=oneoff`, `completion=binary`, `level=need` — bucket items carry no bar, and a bare commitment is a floor, not a stretch), each inheriting the `why`, all tagged together. Ingestion confirms the explode, then writes a `gid` back onto each sub-item. (`level` is shown inline in the change summary as an inferred field, not re-confirmed per item; reassessment can later offer move-to-want or drop per spec §3.)
 
### 3.4 Want-only — symmetric
 
```markdown
- 2x/week volleyball
  - want: 2x per week
  - why: play, move, see people; pure upside, no floor I'm holding myself to.
```
 
→ 1 goal, a single `want`-level version, `recurrence=quota`.
 
### 3.5 Interval, quantity — splits into two goals
 
```markdown
- pushups and pullups
  - need: 50 pushups (4s eccentric) + 20 pull-ups (4s eccentric), every 4 days
  - want: 75 pushups + 30 pull-ups
  - why: when I don't work out I feel gross, and feeling gross has ripple-effect consequences.
```
 
**Resolved as `quantity`** (you want rep counts logged). Pushups and pull-ups are two measures and a version holds one `target_quantity`, so ingestion **splits this into two goals**, each `recurrence=interval` (`every_days=4`, resets via `goal_state.last_completed_at`), `completion=quantity`, unit `reps`:
 
- **pushups** — need 50 / want 75
- **pull-ups** — need 20 / want 30
`why` copied to both. *Note: the qualitative "4s eccentric" lives in `definition` text.*

**Coupled rhythm → rotation group (ADR-0016; retires the v0.4 "acceptable drift" note).** Two independent interval clocks drift into phase and surface both goals the same day — local testing proved this unacceptable. When the real pattern is one alternating rhythm (push → rest → pull → rest), add a `rotate:` line:

```markdown
- pushups and pullups, alternating with rest days
  - (two goal blocks as above)
rotate: [pushups, rest, pull-ups, rest]
```

→ the two goals stay first-class (own need/want bars, own rep logging) and a **rotation group** owns the cadence: exactly one member surfaces per session day, each `rest` consumes one calendar day, a miss holds the pointer so everything downstream shifts. Doing pushups Friday puts pull-ups on Sunday; skipping pushups Friday moves pushups to Saturday and pull-ups to Monday.
 
### 3.6 Accumulation — cumulative target over the chapter
 
```markdown
- spend 4 hours on the painting
  - want: 4 hours total this chapter
  - why: it's mine; the chapter ends and I want paint on canvas, not just intentions.
```
 
→ 1 goal, `recurrence=accumulation`, `config={target:4, unit:hours, window:chapter}`, `completion=duration`. You log time; it sums; done at 4h. Distinct from `quota` (which counts discrete sessions) — accumulation sums a quantity toward one total. Targets are inherently **chapter-scoped**, which fits §5.6.
 
---
 
## 4. Field-by-field disposition
 
`T` = you type · `I` = inferred silently · `C` = LLM proposes, you approve · `sys` = system.
 
| Schema field (§6) | Source in markdown | Disp. | Notes / confirm-trigger |
|---|---|---|---|
| `goal.title` | bullet heading | **T** | Label only; not used for identity. |
| `goal.id` | `<!--gid:XXXX-->` written back | **sys** | Assigned first ingest; §5. |
| `goal.owner_scope` / `person_id` | section heading | **I** | Positional. |
| `goal.chapter_id` | file date header | **I → C** | Goals are **chapter-scoped** (§5.6). Confirm on per-person-vs-shared scoping. |
| `goal.archived_at` | absence on re-ingest | **I** | Auto-archive on removal, reversible, surfaced (§5.4). |
| `goal_version.level` | `need:` / `want:` lines | **I** | Each label → one version at that level (two versions if both). **No label → defaults to `need`** (bare one-offs / explode-bucket items): a commitment is a floor, not a stretch. Explicit label wins. |
| `goal_version.definition` (per bar) | text after the label | **T** | The bar itself. |
| `goal_version.why` | `why:` line | **T (required)** | Authored once; written to all active versions. Ingestion rejects a goal with no why. |
| `goal_version.recurrence_type` | cadence phrasing | **I → C** | Confirm quota-vs-fixed and anything unclear. |
| `goal_version.recurrence_config` | numbers in text | **I → C** | Counts/intervals/weekdays parsed; confirm `week_start`, rotation sequence, loose intervals. |
| `goal_version.completion_type` | bar shape | **I → C** | Variable+logged number → quantity; set/session/abstinence → binary; single timed thing → duration. |
| `goal_version.target_quantity`, `unit` | number in the bar | **I** | Per version. Parsed (`7k`→7000). Null for binary. |
| `goal_version.lifecycle` | default / `paused` | **I** | Defaults `active`. |
| versioning (`version_no`, `effective_*`) | diff vs current | **sys** | §5. |
| `goal_state.*` | — | **sys** | Runtime; seeded on create. |
| `anticipated_obstacle.text` | `obstacles:` bullets | **T (optional)** | One verbatim row per bullet; written to all active versions; no coping parsing. |
| `tag` / `goal_tag` | proposed from text + vocab | **C** | Always confirm — silent tagging drifts vocabulary; batched into one approval. |
| `chapter.label` (theme) | optional after date header | **T (optional)** | |
| `chapter.preamble` | free prose before the first `###` heading | **T (optional)** | Stored verbatim (§2.1). Theme/focus/parked domains; parked is chosen, never slippage — the bot must not nudge toward it. |
| `chapter.start/end_date` | file date header | **I** | |
 
**Net typed surface:** title + one or two bars + why. Obstacles optional. Everything else is off your hands.
 
> **Tags — lightweight by intent.** Tags group goals by life-domain for later filtering and the Tier-3 insights digest; they are *not* identity (two distinct goals may share one). Keep the set small, flat, and stable (~6–8). Starter vocabulary (8): `movement`, `mind`, `admin`, `finance`, `relationship`, `creative`, `diet`, `learning`. The daily loop surfaces by smart-subset, not by tag, so tags have no load-bearing MVP consumer except the insights digest — invest nothing beyond the starter set, and they're a candidate to defer entirely. *(Scope open — §7.)*
 
> **need/want representation — two versions (spec §6 stands).** need and want are **separate `goal_version` rows** (`level='need'`, `level='want'`), both effective at once. This keeps `level` on the row, so `daily_plan_item` pins one version and knows the committed level for free — the spec's removed per-day `classification` does **not** come back. A goal with both bars has two rows that differ in `definition`/`target`/`recurrence_config` and share everything else. `why` + `obstacles` are **written to every active version** of the goal on ingest (you author them once per goal in the md). Duplication across the two rows is accepted — the DB is tiny. *(Alternative, if why-history isn't wanted and version-churn-on-why-edit bothers you: move `why`/`obstacles` to the `goal` identity row. Not adopted by default.)*
 
---
 
## 5. Ingestion contract
 
### 5.1 Identity & ID write-back
- First ingest: each goal gets an opaque ID; ingestion returns your markdown re-marked with an invisible comment on the heading:
  ```markdown
  - step goal <!--gid:STP7-->
  ```
  Invisible in Obsidian preview. Paste it back so IDs persist. One `gid` per goal; exploded one-offs each get their own.
- Re-ingest: **has `gid`** → resolve + diff against current record. **No `gid`** → candidate new goal (ID assigned + written back) unless the duplicate check fires (§5.3).
- **Split goals** (one authored block → N goals, §3.5): all gids ride the shared heading, labeled — `- Pushups and pullups <!--gid:9 pushups--> <!--gid:10 pull-ups-->` — until/unless the author restructures into separate blocks. *(Convention set at first prod ingest, 2026-07-18.)*
### 5.2 New version vs. new goal (surfaced, never guessed)
- **Bar number change is always a new version, same ID** — 7k→8k is tracked evolution, no prompt. Old `daily_plan_item`s stay pinned to the old version (OQ-14); raising a bar never retroactively fails a past day.
- **Large content change** (title + definition + recurrence all shifted, or meaning clearly moved) → confirm "version-bump or new goal?" Default to version-bump; never silently fork identity.
### 5.3 Duplicate warning
A no-`gid` item closely matching an existing goal → warn, don't auto-merge: "looks like *X* — same goal (adopt its `gid`) or new?" Your call.
 
### 5.4 Removal → auto-archive (reversible)
A `gid` goal that has disappeared from the re-ingested markdown is **auto-archived** and listed in the summary ("archived: X, Y — unarchive if unintended"). Reversible. This fits the iterate-from-last-chapter's-md workflow: deleting from the md *is* the human decision. (Distinct from the spec's never-auto-drop, which governs *misses*, not authoring edits.)
 
### 5.5 Chapter rollover (goals are chapter-scoped)
Ingestion distinguishes by the **date header**:
- **Header matches the open chapter** → mid-chapter re-ingest: `gid`s resolve identity, edits → versions (§5.2).
- **Header is a new window** → rollover: a new chapter is created, carried-forward goals become **new goals scoped to it with fresh `gid`s**, and the prior chapter's goals close. Cross-chapter "same goal" lineage is **not** tracked (deferred future-analysis problem). Consequence: psych D-9 (last-chapter hit-rate at bar-setting) has no automatic data source — either defer it or add an optional human-confirmed "link to last chapter's goal" at carry-forward (§7).
### 5.6 What ingestion returns each run
1. **Change summary**, per goal: `NEW` / `VERSION-BUMP` / `UNCHANGED` / `DUPLICATE?` / `ARCHIVED` — with inferred fields (recurrence, completion, tags, owner, chapter) shown inline so silent inferences stay visible.
2. **Confirm queue** — only what needs you: quota-vs-fixed, tag proposals, version-vs-new-goal, bucket explode, pushup-style binary-vs-split.
3. **Re-marked markdown** with `gid`s and any proposed revisions, ready to paste back.
Nothing commits until the confirm queue clears.
 
---
 
## 6. Remaining markdown↔schema friction (flags)
 
1. **Multi-measure goals can't be one quantity goal.** A goal bundling two measured things (pushups *and* pull-ups) has two `target_quantity`/`unit` pairs but a version holds one — so if you want quantity logging, it splits into two goals (§3.5). Binary one-goal avoids the split. Confirmed at ingest. If the split goals share one alternating rhythm, couple them with a `rotate:` line (rotation group, ADR-0016) so their clocks can't drift onto the same day.
2. **Quota vs fixed_schedule** is genuinely ambiguous in English and is the one recurring confirm; `cadence:` pre-empts it, and `fixed_schedule` authored loosely must name its days.
3. **Rotation** doesn't fall out of natural phrasing; needs `cadence: rotation [...]` or a heavy confirm. Lowest priority — no live instance.
4. **Chapter scoping** from one dated file maps to per-person chapters + a shared one; LLM proposes, you approve.
5. **Subtasks under a single one-off** have no goals-db home, and that's intentional — no `parent_goal_id` tree is added to goals-db. MVP: subtasks **fold into `definition` text**, or explode into separate one-offs if independent. When task-tracker integration lands, real subtasks live as parent-child *tasks* there, referenced by the goal (ADR-0005) — not a second tree in goals-db.
6. **`why`/`obstacles` duplicate across the need + want versions.** Accepted — tiny DB; ingestion keeps them in sync by writing to all active versions. (Move to `goal` identity if you ever want to stop this.)
*(Dropped from v0.1: the `if_then` coping column — rejected as over-structure.)*
 
---
 
## 7. Open items for you
 
**Resolved this round:** pushups → `quantity`/split (§3.5); `accumulation` added (§3.6); goals **chapter-scoped** (§5.5); two-version model + accept dup (§4).
 
**Still open (template / ingestion):**
- **D-9 vs chapter-scoping** *(recommend: defer)*: cross-chapter calibration needs lineage you've deferred. Defer D-9 too, or add a nullable `prior_goal_id` set by the human at carry-forward. No chapter-table change either way.
- **Tags in MVP at all?** Starter set is 8 (`movement`, `mind`, `admin`, `finance`, `relationship`, `creative`, `diet`, `learning`). Keep them, or defer tagging until the insights digest needs it (no other MVP consumer).
- **Abstinence goals** (no social media): `daily` + `binary` where "done" = *abstained*. Confirm so the bot frames the win as a non-action ("you stayed off it").
**Architecture-level (belongs in an ADR, not this doc):**
- **Group-profile for shared goals (OQ-16):** model `### Couple` as a `couple` profile that owns the goal (with membership → the two persons), rather than `owner_scope='shared'`. Dissolves OQ-16 (shared goals follow normal recurrence), better fits family expansion, cost = membership + fan-out surfacing. Touches ADR-0004. Template is robust either way.
**Tracked elsewhere:**
- §5 category calls: `interval`/`fixed_schedule`/`paused`/`accumulation` now **in**; others out until needed.
- OQ-COMP-1: how explicitly the bot names a chronic-miss pattern (behavior-spec).
- OQ-PSY-1: upward-recalibration trigger (post-MVP, deferred).
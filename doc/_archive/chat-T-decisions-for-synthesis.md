# Chat T (Goal-markdown) — decisions & edit manifest for synthesis
 
> **What this is:** the graduation list from chat T. The template + ingestion contract itself lives in the companion artifact `goal-markdown.md`; **the items below are the cross-cutting decisions that must land in the spec / ADRs / behavior-spec**, plus the spec-alignment notes the synthesis chat needs. Disposition format matches `synthesis-inbox.md` (MVP/post-MVP · target doc · ADR?/no ADR).
> **Action:** add both this file and `goal-markdown.md` to project knowledge before the synthesis chat runs.
 
---
 
## 0. The template/ingestion contract → `doc/templates/goal-markdown.md`
 
That artifact is the **canonical home** for all authoring/ingestion decisions and needs no further graduation beyond being filed:
- Per-bar `need:` / `want:` labels (canonical; `min:`/`stretch:` aliases dropped) replace `##### Needs`/`##### Wants` section headers; level is a per-bar property.
- Typed surface = **title + bar(s) + why**; obstacles optional; recurrence/completion/tags/owner/chapter/level inferred or confirmed. Cadence parsed from natural phrasing.
- **Two-version model retained** (need + want are separate `goal_version` rows) — *matches spec §6 as-written, no §6 change*; `why`/`obstacles` authored once, written to all active versions on ingest; duplication accepted.
- ID write-back via invisible `<!--gid:XXXX-->`; no-`gid` = new; near-match → duplicate-warn; bar-number change = new version (same ID); large change → version-vs-new-goal **surfaced, not guessed**; removal → **auto-archive (reversible, surfaced)**.
- `if_then`/coping column **rejected**; obstacle bullets stored verbatim, one row each.
- Pushups → `quantity` ⇒ **split into two goals** (pushups 50/75, pull-ups 20/30), interval every 4d.
- `accumulation` added (4h painting).
- Subtasks → **fold into definition text**; no `parent_goal_id` tree in goals-db.
- Tags: 8-set, lightweight (see §3).
---
 
## 1. New decisions — append to `synthesis-inbox.md` as section "## T — Goal-markdown template"
 
- **D-17 — Shared goals (and shared chapters) are owned by a group "couple"/household profile, not `owner_scope='shared'`.** A shared goal becomes an ordinary goal owned by a group profile (membership → member persons), inheriting all recurrence/completion semantics and **deleting the `owner_scope`/null special-case on both `goal` and `chapter`**. Dissolves OQ-16 (reset-vs-persist follows the goal's `recurrence_type`). Scales to family expansion, which `owner_scope='shared'` can't (no group identity / multiple sharing groups). Cost: a membership relation + fan-out surfacing (group goals surface into each member's morning; either completes). → **MVP (build now, skip the retrofit) · profile/data-model + spec §6 + architecture · ADR (revises ADR-0004).** *(chat T, OQ-16)*
- **D-18 — Goals are chapter-scoped; cross-chapter lineage deferred.** A goal belongs to one chapter (`goal.chapter_id` FK — the chapter table already exists in §6; **no jsonb goal-id array** — that denormalizes a relationship the FK models correctly). Within a chapter, `gid` resolves identity and edits → versions. At rollover (new date header), carried-forward goals become **new goals scoped to the new chapter** with fresh `gid`s; the prior chapter's goals close. "Same goal across chapters" is a deferred future-analysis problem. → **MVP · spec §4/§6 · no ADR.** *(chat T, OQ3)*
- **D-9 → DEFERRED (modifies R1 D-9).** Proactive calibration (show last chapter's actual hit-rate next to each proposed bar) requires cross-chapter lineage, which D-18 defers. Deferring D-9 is the consistent call. If wanted later, the cheap mechanism is a nullable `prior_goal_id` on the new goal set by the human at carry-forward — **not** a chapter-table change. → **post-MVP · update psychology.md D-9 + spec · no ADR.** *(chat T, OQ3 follow-up)*
---
 
## 2. Spec `goal-bot-spec.md` §6 — schema edits
 
- **Add `accumulation`** to `goal_version.recurrence_type` enum. `recurrence_config = {type:'accumulation', target:N, unit:X, window:'chapter'}`; `completion_type` carries the unit (`duration` for hours, `quantity` for books/$). Sums logged progress toward a chapter target.
- **Confirm `paused`** stays in `goal_version.lifecycle` (dormant, not dropped) — now exercised by the template.
- **Group-profile (D-17):** replace `goal.owner_scope`+`person_id` and `chapter.owner_scope`+`person_id` with a single `owner_profile_id` → `profile.person`/group profile; add a membership relation (`group_profile_id → member person_id`). Removes the `'shared'`/null special-case.
- **No change** to the `goal` ↔ `goal_version` two-version split — the template aligns with §6 as-written.
---
 
## 3. Spec behavior edits (§3–§5) / behavior-spec
 
- **Chapter-scoped goals + rollover semantics** (D-18) — §4.
- **D-9 deferred** — remove from MVP chapter-setting flow; note as post-MVP (§3 / OQ list).
- **§5 category calls (resolves the open §5 item):** `interval`, `fixed_schedule`, `paused`, **`accumulation`** are **IN** for MVP (the template exercises them). Others (`scale`/rating) stay out until a goal needs them. **Jade's gym = `quota`** (not `fixed_schedule`).
- **Auto-archive on md-removal** is distinct from the spec's never-auto-drop principle — never-auto-drop governs *misses*; deleting a goal from the authored md is a deliberate human edit. Record so they aren't read as conflicting.
- **Abstinence goals** (e.g. no social media) = `daily` + `binary`, where "done" = *abstained*; frame the win as a non-action ("you stayed off it").
- **Tag starter vocabulary (8):** `movement`, `mind`, `admin`, `finance`, `relationship`, `creative`, `diet`, `learning`. Flat, grow on demand. Lightweight: no MVP consumer except the Tier-3 digest, so safe to keep minimal or defer.
---
 
## 4. ADR / index implications
 
- **New ADR — group-profile for shared identity** (D-17), revising **ADR-0004**; set ADR-0004 status → `Superseded by ADR-00NN` (append-only rule). Update `index.md` in the same commit.
- **Optional ADR — ingestion identity & reconciliation** (ID-by-`gid`, version-vs-new-goal surfaced, duplicate-warn, auto-archive). It's an implementation of the already-decided OQ-5 identity-by-ID rule; worth its own ADR only if you want a guardrail a future ingestion change can't silently violate. Lean: capture in the template doc + a one-line ADR pointer rather than a full ADR.
---
 
## 5. Resolved / dissolved
 
- **OQ-16** — dissolved by D-17 (shared goals follow normal recurrence semantics; no special reset-vs-persist question). Mark resolved in spec §10.
## 6. Still open (carry forward)
 
- **OQ-COMP-1** — how explicitly the bot names a chronic-miss pattern back to the user (behavior-spec; profile-divergent framing). *Unchanged.*
- **OQ-PSY-1** — upward-recalibration trigger definition (post-MVP, deferred). *Unchanged.*
- **D-9** — parked (post-MVP), see §1. Not "open," just deferred.
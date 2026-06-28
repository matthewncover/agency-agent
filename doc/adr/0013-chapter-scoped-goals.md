# ADR-0013: Goals are chapter-scoped; cross-chapter lineage deferred
 
**Status:** Accepted
 
## Context
Chapters are the goal-setting blocks (spec §4). Chat-T (D-18) had to decide how goal identity relates to chapters across a rollover: does a goal persist as one identity across chapters (cross-chapter lineage), or is each chapter's goal a fresh identity? Cross-chapter lineage is the thing proactive last-chapter-hit-rate calibration (psych D-9) would need. Tracking "the same goal" across chapters is a real future-analysis problem (matching, drift, renames) that isn't needed for a working MVP loop.
 
## Decision
- A goal **optionally belongs to one chapter** via **`goal.chapter_id`** (FK, **nullable**). The chapter table already exists (§6); this is a single FK, **not** a denormalized jsonb goal-id array.
- **`chapter_id` is nullable**: chapter-less goals are allowed and simply persist across windows untouched (no rollover behavior applies to them).
- For **chaptered** goals: within a chapter, the markdown `gid` resolves identity and edits become versions (the existing identity-by-ID + versioning rules, ADR-0004→0012 / OQ-5 / OQ-14).
- At **rollover** (a new chapter window in the authored markdown): carried-forward goals become **new goals scoped to the new chapter with fresh IDs**, and the prior chapter's goals close. "Same goal across chapters" lineage is **not** tracked for MVP — it's a deferred future-analysis problem.
- **Soft invariant (confirm-at-ingest, not a DB constraint):** a group-owned goal living inside an individual's private chapter is the one odd combination worth flagging at ingest; ownership equality between a goal and its chapter is otherwise not enforced (Matthew's non-rigid steer).
## Consequences
- The identity model stays narrow: identity resolves *within* a chapter, which keeps `gid` reconciliation tractable.
- **Psych D-9 (proactive hit-rate at bar-setting) becomes post-MVP**, because it requires cross-chapter lineage this ADR defers. If wanted later, the cheap mechanism is a nullable `prior_goal_id` on the new goal set by the human at carry-forward — **not** a chapter-table change. Nothing in the MVP loop assumes D-9.
- Versioning/pinning (OQ-14) is unaffected *within* a chapter; raising a bar mid-chapter is still a new version, not a new goal.
- Rollover is a clean, non-punitive fresh start (aligns with the chapters-as-fresh-start intent) without carrying a hidden cross-chapter identity graph.

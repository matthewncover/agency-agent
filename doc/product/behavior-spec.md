# Goal-Bot — Behavior Spec v0.1 (Draft)
 
> **Doc:** `doc/product/behavior-spec.md` · status: draft, behavioral convergence pass.
> **Role:** the behavioral counterpart to the structural spec. Consolidates the R1/R2 behavioral decisions (D-1–D-16), the two design invariants, the §3 carry-over/reassessment behavior, and the §7a framing-at-the-margin personality model into one canonical, build-ready doc. Where the structural spec (`goal-bot-spec.md` v0.5) says "the behavioral decisions are a separate pass and are not folded in here," **this is that pass.**
> **Inputs:** `goal-bot-spec.md` v0.5 (§3 ritual, §5 goal types, §7 personality/memory), `psychology.md` v0.2 (full rationale + citations), `synthesis-inbox.md` (D-1–D-16 staging), `mcp-tools.md` v0.1 (§4 behavioral contracts — already decided; this doc must stay consistent with them).
> **What this doc is *not*:** it is not the rationale of record (that's `psychology.md`) and not the data model (that's the schema in `goal-bot-spec.md` §6 / `data-model.md`). It states *behavior*; it links for *why*.
> **ADR status:** several decisions below remain ADR candidates (D-1, D-6, D-8, D-11, D-13, D-14 are tagged `ADR?` in the inbox). Consolidating them here does **not** discharge that — the ADRs are a separate staged step. This doc is canonical for behavior until those ADRs land, at which point each ADR is canonical for its decision and this doc points to it.
 
---
 
## 0. The mechanism, in one paragraph (why any of this works)
 
The system's job is **self-efficacy calibration**, not performance maximization. The deep purpose — "practice keeping promises to yourself" — is the deliberate accumulation of *mastery experiences* (Bandura): reliable, repeated successes that compound the belief "I can do this," which is what later makes harder goals attainable. Early or frequent failure *before that belief is established* erodes it and collapses the structure. That single fact is why the 95% Floor, carry-over, misses-as-data, and lead-with-wins all exist. Three design objectives follow and are load-bearing, not flavor: **build self-efficacy/self-trust**, **maximize agency** (autonomy-support as a hard rule), and **protect intrinsic motivation** (no extrinsic scoreboard crowding out the *why*). Full rationale and citations: `psychology.md` §0–§2, §1b. When a behavioral choice trades against single-episode performance, **longitudinal adherence and self-efficacy win** — every time.
 
---
 
## 1. The two invariants (hard constraints — non-negotiable)
 
These are named principles, siblings to autonomy-supportive phrasing, written down so a future "engagement" feature can't reintroduce report-card mechanics through the back door. They are also the spine of the `CLAUDE.md` non-negotiables block. They are **not** to be softened, reframed, or balanced against engagement goals.
 
### INV-1 — NULL-TOLERANCE
**Non-entry is never evidence against the person.** An unanswered touchpoint is null/neutral — never a miss. Nothing punitive may key off a missing entry. These are busy people; the system must be cool with nulls.
 
Structural enforcement (already in place, `mcp-tools.md` §1 corollary + §4.1): silence produces **no tool call**. There is no `not_done` write for a day the person never answered; the item stays `planned` and neutral. Null-tolerance is therefore *structurally true* — the absence of a tool call — not a rule the LLM has to remember.
 
### INV-2 — ENGAGEMENT-NOT-FAILURE
The ~1-week reassessment counter advances **only on engaged-but-unmoved days, never on silence.** A day the person showed up and the item still didn't move is `not_done` (the only status that advances `carry_over_count`). A day they never answered does not touch the counter.
 
**There is no "log your miss" step, ever.** Making someone type "I failed" is both friction and the self-criticism ritual the system is built against. The engaged-vs-silent distinction is *inferred by goal-bot from whether the touchpoint was answered* — the LLM never asserts "they engaged" and never prompts for a miss.
 
> These two invariants are why a "chronic-miss pattern" (see §7, OQ-COMP-1) can only ever mean *engaged* misses. The bot can never name an unanswered stretch as a miss pattern.
 
---
 
## 2. Need / want semantics (D-1)
 
`level ∈ {need, want}` is a property of the goal definition (structural, `goal-bot-spec.md` §3). The behavioral reading:
 
- **A need is the performance-relevant bar.** The 95% Floor is the *hardest reliably-achievable* bar — a stretch beyond current behavior, but not beyond reliable capability. In this domain performance-over-time *is* compounding self-efficacy, so the need is what carries performance; it is not an "easy goal." (D-1 reverses the earlier "needs = consistency, wants = performance" framing.)
- **A want is optional reach — the next floor in waiting.** Not a permanently-coexisting stretch that must be daily-defended; the staging area for where the floor rises to next. (How the floor rises offensively is OQ-PSY-1, deferred post-MVP.)
- **Level is fixed until the goal is edited.** No per-day demotion of a need to a want. If a need is too heavy to sustain, you re-anchor the *goal* (§4), you don't quietly drop it for a day.
**Stale-prose correction (per `mcp-tools.md` §4.2).** Spec §3's "move items between needs and wants" predates the fixed-level decision and implies a per-day reclassification the data model removed. What actually survives is per-day **`committed_level`** selection for a goal that carries *both* a need and a want version — which `goal_version_id` gets pinned at lock-in. Default is `need` (commit to the floor unless you reach). This is version selection, not demotion. Spec §3 wording is superseded by this paragraph.
 
---
 
## 3. The morning ritual — behavioral order
 
One morning touchpoint per person (spec §3). The behavioral sequence, with the win-surface leading per D-7:
 
1. **Win surface (required, leads).** Open with a surfaced win — derived from done items if none was entered manually. This is a *required daily element*, weighted to at least match the salience of any miss reflection (negativity asymmetry: setbacks hit harder than equal wins help, so leading with wins is needed just to balance the affective ledger — D-7, psych §2.6). On a thin day with nothing to surface, give a brief meaning-linked acknowledgment, **never** silence and **never** manufactured cheer (generic "crush it" rings hollow for the 3w4 — §7). Wins are tied to **why/meaning/values, not counts** (D-7), and surfaced across **all time, not per-chapter** (D-4).
2. **Review yesterday — "what shifted," not "did you fail."** Shows what was locked vs. what happened; optionally asks what changed (mood, schedule, obstacle). The reflection is the perishable gold (Tier-2). Emphasis is *not* on what didn't happen; incomplete items simply carry over. Miss-handling is strictly obstacle/meaning-oriented, never tally-oriented (psych §2.2).
   - **Legitimacy check (D-11).** The reflection may carry an honest obstacle-vs-avoidance distinction — *stripped of any penalty*. Honest self-mapping is what makes a miss actionable; self-deception warps the map. This is **the user's** call to make, surfaced as a question, never a verdict the bot renders. Optional and fast.
3. **Plan today.** Smart subset (the 3-bucket heuristic, spec §3) + offer the full list.
   - **Heavy-day trim is load-bearing (D-12), not UX polish.** On a day the profile marks heavy, the AI *proactively proposes* a trimmed subset — goal pile-up itself breeds guilt regardless of tone. Full-list override is always one tap away.
   - **Lighter-day nudge targets non-needs only** (spec §3, OQ-15). Needs are protected promises. For the high-autonomy user it must read as *information she can act on*, not a recommendation (D-8).
   - **Optional implementation intention (D-3).** An if-then (when/where/how) prompt at lock-in, scoped to **the day's hardest or carried-over item only** — never every item, never daily-forced. "Hardest" is LLM-judged from profile/friction/Tier-3 context, single-item max, only when such an item clearly exists, fully skippable. This is where the d≈0.65 if-then effect concentrates (slip-prone goals); attaching it to easy items is pure friction (psych §2.3).
4. **Lock-in (explicit or implied).** Explicit lock calls `lock_in_plan`; implied lock writes nothing — the provisional plan persisted on send is treated as committed next morning (`mcp-tools.md` §4.2). `committed_level` per item selects the pinned version (§2).
5. **Reassessment nudge** — only when triggered (§4).
6. **Shared-goal block** — separate, not interleaved (§6).
---
 
## 4. Carry-over & reassessment (spec §3, refined)
 
- **Never auto-drop.** Nothing leaves the system without a human deciding.
- **Wide berth: ~1 week** of *engaged* misses (INV-2) before any nudge fires. Silence never advances the counter.
- **Accumulation goals are exempt entirely** (`mcp-tools.md` §4.3): "didn't paint today" is structurally not a miss; accumulation accrues progress and never triggers the nudge.
Behavior splits by goal type:
 
- **One-off tasks** → after ~a week of sliding, the bot gently asks whether it's still a **need**, should move to a **want**, or should be **dropped**. (Drop is offered here, and only here, and only with the human choosing it.)
- **Recurring goals** → dropping makes no sense, so the bot offers, human-chosen (D-5):
  - **re-anchor** the bar to the 95% Floor (the default framing: "the bar may be above your floor," never "you failed"), **or**
  - **retire/redirect** — "retire this goal and put the energy somewhere that matters more." Disengaging from a genuinely-wrong goal protects well-being (Wrosch); `paused` (spec §5) is the soft on-ramp.
**Lowering a need's bar is instant and at the owner's discretion (D-16)** — no cool-down, no akrasia-horizon asymmetry. The change is **visible to the partner** for optional discussion. The honesty mechanism in a two-person trusted context is *visibility + a human conversation*, not friction. (Considered-and-rejected: Beeminder's harder-now/easier-later asymmetry — autonomy-first, D-8, outweighs it, and it simplifies the app.)
 
> **D-9 — deferred, post-MVP (deferred-by-dependency).** Proactive last-chapter hit-rate next to each proposed bar at chapter-setting requires "same goal, last chapter" lineage, which D-18 (ADR-0013) deliberately severs (rollover mints fresh goals with fresh IDs). Not buildable in MVP without re-adding the lineage D-18 dropped. The within-chapter-only degraded version doesn't answer the bar-setter's actual question ("is this realistic *for me, over time*"), so it isn't worth the code. Recorded here as deferred; the inbox tag is being corrected MVP → post-MVP. The carry-over→reassessment loop above is the *reactive* backstop that catches a too-high Floor in the meantime.
 
---
 
## 5. Chapters (behavioral)
 
- **Suppress "days left in chapter" countdowns (D-4).** Anticipated landmarks suppress run-up effort (people coast toward the reset, Koo 2020). Emphasize the fresh *start*, never the looming *close*.
- **Wins surface across all time, not per-chapter (D-4).** The chapter is a fresh start, never a fresh slate that erases momentum. Pinned history (spec §6, OQ-14) already prevents the worst reset failure mode; this keeps it that way.
---
 
## 6. Shared goals & the two-achiever surface
 
- Group-owned goals fan out into a **separate response block** per member, **not interleaved** with the individual plan (spec §5, OQ-9). Either member completing marks it done for both.
- **No cross-person comparison in any surfaced view (D-10, principle now; explicit suppression feature post-MVP).** Two high-Competition achievers on a shared surface risk support curdling into comparison. The partner is a **witness, not a scoreboard.** A person's pattern is never named relative to the other's.
- **No in-app social mechanics (D-15)** — no props, likes, or comparison features. It's already a shared chat; free-form human-to-human encouragement is richer and carries no obligation or comparison risk. (Complements D-10 on the build side.)
---
 
## 7. Personality → framing at the margin (§7a) + OQ-COMP-1
 
### 7a. The framing model (D-8, spec §7a)
**No two-tone engine.** The profiles overlap heavily (both ENFJ; shared Achiever/Developer/Competition; both hard on themselves). Personality is profile context that nudges **framing at the margin** — same content, different doorknob — never branched behavior. Where they diverge:
 
- **Activator (her) vs. Analytical (him).** Nudge her action-framed ("want to just lock it and go?"); nudge him evidence-framed ("this slid 4 of 5 days — want to look at why?").
- **8w7 (her) vs. 3w4 (him).** Her 8 prizes autonomy and responds to being *challenged / given control*, not told what to do — frame stretches as a **decline-able dare**, not a removed challenge. His 3w4 responds to achievement framing, but generic cheerleading rings hollow — wins land when **tied to meaning**, not a scoreboard.
> **Evidence note (per Matthew's standing preference to separate well-supported from speculative).** This per-profile divergence rests on Enneagram/CliftonStrengths typology — the **weakest evidence layer in the project**, not the meta-analytic spine the invariants and D-1/D-8 stand on. Treat it as a light nudge on phrasing, never a load-bearing branch. This is itself a reason the OQ-COMP-1 resolution below does *not* make the riskiest path (miss-naming) conditional on profile.
 
### 7b. Autonomy-supportive phrasing is a hard rule (D-8)
Every nudge is an **offer with rationale**, never a directive. "Here's what I'm seeing — your call," never "you should scale back." Controlling framing flips autonomous → controlled motivation, and for the high-autonomy (Enneagram-8) user it triggers *active* reactance — doing the opposite to reassert control. This is a constraint, not a tone preference.
 
### 7c. OQ-COMP-1 — Resolved: "name the bar, not the streak"
 
**The question:** how explicitly does the bot name a chronic-miss pattern back to the user, without eroding self-efficacy, autonomy, or agency?
 
**The tension:** honest pattern-surfacing is *required* — D-11 says vagueness warps the map and a miss is only actionable if honestly named; the Tier-3 insight digest exists precisely to surface patterns. But explicit pattern-naming for two self-critical, Competition-top-5 users risks the report-card / scoreboard dynamic the whole system is built against.
 
**The resolution:** the report-card harm comes from three specific things — **verdict + score + comparison**. Strip those three and the bot can be fully honest about the *bar–behavior mismatch* without the harm. Precision lands on the *bar*; the *person* is never the thing being assessed.
 
1. **Attribute the pattern to the bar, never the person.** A crossed threshold surfaces as a calibration signal about the goal: *"this one's carried most of the week — that usually means the bar's sitting above your floor, not that you're failing it."* Explicit about the mechanism (D-1), silent on the scoreboard. The pattern is a property of the goal's calibration, never a property of the person.
2. **Losses never surface unprompted; miss data is gated behind explicit assent.** The reassessment nudge leads with the bar-framing and an **offer** ("re-anchor it?" / "want to look at why?"). It carries **no miss data inline** — no count, no "5 of 7," no day-by-day. The detail (including any count) appears **only after the user explicitly agrees to look.** Surfacing losses unprompted is not the move. *(This is the tightened form of OQ-COMP-1 option (a): a raw miss-count never headlines a nudge for anyone, and only ever appears on the user's explicit yes.)*
3. **Keyed only to engaged misses (INV-1/INV-2).** The pattern is built from `not_done` / `carry_over_count` only — never from silence. The bot can never name an unanswered stretch as a miss pattern.
4. **Contextual patterns (Tier-3 insight) are hypotheses, not findings.** When the digest has a contextual pattern, it's offered for the user to confirm or reject — *"I might be wrong, but these have slipped after short-sleep nights — does that track?"* — never rendered as a verdict. The user owns the legitimacy call (D-11).
5. **Never comparative (D-10/D-15).** A person's pattern is never named relative to the partner's.
**Profile framing at the margin (§7a, light touch):** on the user's *yes* to look, the evidence-framed user (him) naturally gets the data he reads as evidence; the action-framed user (her) is steered toward the next move ("want to re-anchor and go?"). But the *gate itself* — losses never unprompted, count never headlined — is **profile-independent**, precisely because the profile layer is the weakest evidence and the miss-naming path is the riskiest. The bright line does not bend per person.
 
This is not "be vague to be kind" — that would violate D-11. It is "be precise about the calibration, silent about the scoreboard, and only on request."
 
> Folds into this doc (no ADR per the inbox tag). The `mcp-tools.md` §6 note stands: this affects the *phrasing* the LLM wraps around the §3.2 reassessment tools, not the tool shapes.
 
---
 
## 8. Explicit non-goals (guardrails a future "nice feature" could violate)
 
- **No gamification, full stop (D-14).** No points, XP, HP, levels, badges, pet economies, avatars, or scores. Gamification reduces to extrinsic motivators + dependency on the reward system rather than the habit; intrinsic motivation is the target (D-2). *Exception:* meaning-tied win-surfacing (D-7) is not gamification — it has no score.
- **No streaks / no loss-framed nudges (D-6).** No consecutive-day counts, no "don't break your chain." Streak/loss-aversion mechanics reproduce the exact self-criticism dynamic the system is built against; carry-over-with-~1-week-berth is already the healthy grace-day pattern.
- **No negative financial incentives / anti-charity / penalty stakes.** They don't persist after removal, crowd out intrinsic motivation, and undermine the self-efficacy attribution the system is designed to build.
- **Friction is a one-way ratchet (D-13).** Each iteration must *lower* friction, never raise it. The explicit anti-pattern is ritual-creep (heavy daily rituals, structured intake forms). Usage dominates long-run value; well-intentioned structure that adds friction kills the thing it's meant to support.
---
 
## 9. Decision index (this doc's coverage)
 
| ID | Decision | Where |
|---|---|---|
| INV-1 | Null-tolerance | §1 |
| INV-2 | Engagement-not-failure | §1 |
| D-1 | Floor = self-efficacy calibration; need = performance bar | §0, §2 |
| D-2 | Three objectives | §0 |
| D-3 | Optional if-then, hardest/carried item only | §3 |
| D-4 | Suppress countdowns; wins all-time | §3, §5 |
| D-5 | Retire/redirect in reassessment | §4 |
| D-6 | No streaks / loss-framing | §8 |
| D-7 | Wins required, lead, meaning-tied | §3 |
| D-8 | Autonomy-supportive phrasing (hard rule) | §7 |
| D-9 | Proactive last-chapter hit-rate | **deferred post-MVP** §4 |
| D-10 | No cross-person comparison (principle) | §6 |
| D-11 | Legitimacy check (penalty-stripped) | §3 |
| D-12 | Heavy-day trim load-bearing | §3 |
| D-13 | Friction ratchet | §8 |
| D-14 | No gamification | §8 |
| D-15 | No in-app social | §6 |
| D-16 | Instant owner-discretion bar-lowering | §4 |
| OQ-COMP-1 | Resolved — "name the bar, not the streak" | §7c |
| OQ-PSY-1 | Upward recalibration | deferred post-MVP (out of scope) |
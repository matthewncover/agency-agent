# Psychology Research — Motivation & Behavior Change, Mapped to Goal-Bot Decisions
 
> **Doc:** `doc/research/psychology.md` · **v0.2** · status: Phase-1 (R1) output, decisions folded in
> **Role:** Survey the motivational and behavior-change literature relevant to goal-bot's *specific* design, tag each spec decision **Supports / Challenges / Modify**, and record the resulting calls. Input: `goal-bot-spec.md` v0.4. This doc does not rewrite the spec; §4 records the decisions it produced, which feed `synthesis-inbox.md` → ADRs → the updated spec (per meta-plan §6).
>
> **Changelog v0.1 → v0.2:** §2.1 rewritten — the 95% Floor is reframed as **self-efficacy calibration** (Bandura added as the missing pillar) and the Locke-Latham "tension" is demoted to an *apparent* tension that resolves once the domain/dependent-variable mismatch is named; the need is now understood as *calibrated-hard*, not easy, and as the performance-relevant bar for this domain. Autonomy (§2.8) elevated from framing-at-the-margin to a **design objective** (agency-maximizing). Anti-streak stance and intrinsic-motivation-as-objective written in (§1b, §3). Abandonment path, countdown suppression, wins-across-all-time, wins-tied-to-meaning confirmed. Original "open questions for you" (§4) converted into a decisions record + one new residual (upward recalibration).
>
> **Evidence-quality note:** two popular "accountability" figures (the "95% with a partner" ATD stat and Gail Matthews' "+33 points") are weak — Matthews was never peer-reviewed, the ATD number is routinely mangled. Load-bearing anchors are meta-analytic (Harkin 2016; Gollwitzer & Sheeran 2006; Neff 2023; Bandura 1997).
 
---
 
## 1. Executive summary
 
The spec's architecture is well-aligned with the evidence. After review, the one item flagged in v0.1 as "the big tension" largely dissolves, and the rest are refinements — most now adopted.
 
**The 95% Floor vs. goal-setting theory is not the conflict it first appears.** Locke & Latham's "specific, *difficult* goals win" finding has three boundary conditions, and the decisive one is a domain mismatch: that literature measures *performance on a task, conditional on attempting it*, usually a single short-horizon episode with an assigned goal. Goal-bot's domain is *longitudinal, self-directed adherence*, where the binding constraint is showing up repeatedly and the scarce resource is **self-efficacy** — which is *endogenous*, built or destroyed by the outcomes you produce. Bandura's most-replicated finding is that self-efficacy is built primarily through **mastery experiences** (actual successes) and is undermined by failure *especially before efficacy is firmly established*. That is exactly the spec's own thesis — "practice keeping promises to yourself" — given a mechanism. So the 95% Floor is not an "easy goal"; it is the **hardest reliably-achievable** bar (the edge of capability where success is still near-certain), which is a *stretch beyond current behavior* even though it is *not a stretch beyond reliable capability*. In this domain the **need is the performance-relevant bar**, because performance-over-time *is* compounding self-efficacy; the **want** is optional reach and the staging area for the next floor, not the load-bearing driver.
 
**Strongly supported and kept:** morning monitoring ritual (progress monitoring is among the better-evidenced self-regulation levers, d+≈0.40, stronger when recorded/shared — which the two-person chat delivers for free); misses-as-data reframing (self-compassion research is unusually clean, and is *specifically* protective for high-achievers who run hard on themselves); lock-in as a penalty-free commitment device; carry-over + reassessment over dropping; surfacing wins (progress principle).
 
**Refinements, now decided (see §4):** add an *optional* implementation-intention (when/where/how) prompt scoped to the day's hardest or carried-over item only; suppress chapter-end countdowns (keep the fresh-*start*, drop the anticipated-*ending* drag); add a genuine-abandonment path to recurring-goal reassessment; make autonomy-supportive (offer-not-directive) phrasing a hard rule; write "no streaks / no loss-framed nudges" in as an explicit non-goal; tie surfaced wins to meaning/values and surface them across all time, not per-chapter.
 
**One new residual (§4):** the spec's recalibration is purely *defensive* (it lowers a too-high bar after misses). The self-efficacy model implies a missing *offensive* counterpart — a signal that notices a floor cleared with room to spare and offers to raise it. Without it, upward iteration relies on the human spontaneously raising bars.
 
---
 
## 1b. Design objectives this research surfaces
 
The spec's §1 lists three objectives (maximize likelihood of meeting goals; low friction; fit our psychology). The research supports adding/sharpening three more, each evidence-backed:
 
- **Build self-efficacy / self-trust (operationalizes the spec's existing "keep promises to yourself").** Mastery experiences are the engine; the system should be biased toward producing reliable wins that compound belief, and toward *never* manufacturing early failures that erode it. This is the deep "why" behind the 95% Floor, carry-over, and misses-as-data. *(Bandura 1977, 1997.)*
- **Preserve and maximize agency (autonomy-support as a hard rule).** Not a tone flourish — an objective. Controlling framing shifts a person from autonomous to controlled motivation, and for the high-autonomy user it actively triggers reactance. Every nudge is an offer with rationale, never a directive. *(Ryan & Deci 2000; Brehm 1966.)*
- **Protect intrinsic motivation (avoid crowding-out).** Keep the *why*/meaning salient alongside any metric; never let counts, completion rates, or (especially) streaks become the scoreboard the system optimizes, because salient extrinsic markers crowd out the intrinsic motivation that sustains long-run adherence. *(Ryan & Deci 2000; Deci 1971.)*
These three are mutually reinforcing (all three are SDT's needs — competence/autonomy/relatedness — plus its internalization continuum) and they are what make the difference between a system that feels kind and one that actually compounds.
 
---
 
## 2. Findings by design decision
 
### 2.1 The 95% Floor — self-efficacy, planning fallacy, goal-setting theory
 
**Tag: Supports (tension resolved)**
 
Two literatures justify the Floor; a third only *appears* to threaten it.
 
**(a) Self-efficacy is the primary justification (was under-weighted in v0.1).** Bandura's self-efficacy — the belief you can execute the actions a goal requires — is one of the strongest predictors of commitment, persistence, and resilience after setbacks. Its four sources are mastery experiences, vicarious experience, verbal persuasion, and physiological state; **mastery experiences (actual successes) are the most powerful**, and failures undermine efficacy *particularly when they occur before a sense of efficacy is firmly established*. That last clause is the entire case for starting at a reliably-clearable floor: early, repeated success is what builds the belief that later makes harder goals attainable. The spec's intuition — that setting many hard goals and failing early reinforces "I can't do this," erodes self-trust, and collapses the whole structure — is not folk psychology; it is the standard reading of the mastery-experience literature. The spec's stated deep purpose, "practice keeping promises to yourself," *is* the deliberate accumulation of mastery experiences. The Floor, carry-over, and misses-as-data all serve this single objective.
 
**(b) Planning-fallacy correction is the secondary justification.** Buehler, Griffin & Ross (1994) showed people systematically underestimate their own completion times — predicted ~34 days vs. ~56 actual in their core study — and, decisively for a "95% sure" bar, even when people gave times they were **99% certain** of, only ~30% finished by then. So a naive self-reported "95% confident" bar is itself optimistically miscalibrated. The Floor's framing ("given all the ways you tend to betray and sabotage yourself, and real variance") is the documented corrective: it forces the *outside view* and *past-experience recall* that the planning fallacy otherwise skips. The carry-over→reassessment loop (§2.4) is the empirical backstop that catches a Floor still set too high.
 
**(c) The Locke-Latham "tension" resolves on scope.** The most-replicated goal-setting result — specific, difficult goals beat "do your best," effect sizes ~.42–.80 — has three boundary conditions:
1. **Built-in moderators.** Locke & Latham hold the difficulty→performance effect *only when commitment and self-efficacy are high*, and it is **not monotonic** — beyond the person's ability ceiling, performance falls. "Harder is better" was never unconditional even in their own theory.
2. **Domain.** The subset of the goal-setting literature closest to goal-bot's domain — sport/health — already departs from the org/lab pattern: a meta-analysis found only *moderately* difficult goals reliably help, and over a third of sport studies found specific-hard goals didn't even beat "do your best." The closer the evidence gets to your actual problem, the weaker "set hard goals" becomes.
3. **Dependent-variable mismatch (the crux).** Locke-Latham measures *performance on a task, conditional on attempting it* — typically one episode or a short window, often an assigned goal, then the study ends. It does **not** measure whether you keep showing up over months while your belief about yourself compounds or collapses. Goal-bot's binding constraint is adherence, gated by self-efficacy, which Locke-Latham holds constant and goal-bot cannot.
**Net:** the Floor is not an "easy goal" in the Locke-Latham sense (their "easy" = below-capability, low-effort). It is **calibrated-hard** — the highest bar that is still ~95% reliable — which lands in the *moderately difficult* band that actually works in habit/health contexts, and which is a genuine stretch *from current behavior* (if you weren't already doing it, the floor is a behavior change) without being a stretch *beyond reliable capability*. In this domain the **need carries performance**; the **want** is optional reach and the staging area for the next floor.
 
**Design implications:** keep the need as the protected, reliably-clearable, performance-relevant bar. Keep wants as optional reach, explicitly understood as "next floor in waiting" rather than a permanently-coexisting separate stretch that must be daily-defended. (The residual question — how the floor *rises* — is in §4.)
 
**Citations:** Bandura (1977), *Psych. Review* 84:191–215; Bandura (1997), *Self-Efficacy: The Exercise of Control*; Buehler, Griffin & Ross (1994), *JPSP* 67:366–381; Locke & Latham (2002), *Am. Psychologist* 57:705–717; Klein et al. (1999), *Psych. Bulletin* 125(1); sport meta: Kyllo & Landers (1995); Williamson et al. (2022) review.
 
---
 
### 2.2 Morning-only ritual + "misses as data, not verdicts" — self-compassion vs. self-criticism
 
**Tag: Strongly Supports**
 
The cleanest support in the survey, and it matters most *because* both users are high-achievers who run hard on themselves — the population where self-criticism does the most harm and self-compassion the most good.
 
The monitoring half is well-evidenced alone. Harkin et al. (2016) — 138 studies, ~20,000 participants, experimental only — found interventions reliably raised monitoring frequency (d+ = 1.98) and promoted attainment (d+ = 0.40), with **larger effects when outcomes were reported/made public and physically recorded**. A daily morning check-in that records what happened *is* such an intervention, and the shared two-person chat satisfies the recorded/public moderators for free (see §2.7).
 
The misses-as-data reframing is directly validated. Neff's review: self-compassion is negatively related to maladaptive perfectionism but positively associated with high performance standards and initiative — self-compassionate people aim high *and* accept they can't always hit the target. The single most on-point study is Hope et al. (2014): higher self-compassion predicted lower negative affect on days when goals were not achieved, and self-compassionate people focused more on whether goals were personally meaningful than on success/failure. That is almost exactly the nightly dynamic the spec engineers — a miss should produce obstacle/meaning reflection, not an affect hit that triggers the self-criticism loop. The mechanism (self-criticism runs on a threat/fear system; self-compassion on the care system) is what justifies the report-card avoidance.
 
**Negativity-asymmetry caveat (from §2.6):** setbacks hit harder than equivalent wins help. This is the empirical reason the morning-only (no evening report-card) design and the lead-with-wins posture are not cosmetic — they're needed just to balance the affective ledger for two self-critical achievers.
 
**Design implication:** keep miss-handling strictly obstacle/meaning-oriented and never tally-oriented.
 
**Citations:** Neff (2023), *Annual Review of Psychology* 74:193–217; Hope, Koestner & Milyavskaya (2014), *Self & Identity*; Harkin et al. (2016), *Psych. Bulletin* 142(2).
 
---
 
### 2.3 Needs vs. wants, lock-in as a promise — implementation intentions, commitment devices
 
**Tag: Supports (lock-in) + adopted Modify (optional if-then, tightly scoped) + Watch (no-penalty is correct)**
 
Lock-in is a commitment mechanism, and committing to a concrete plan is where intentions convert to behavior. But the literature is specific about *which* plan format carries the effect.
 
Goal intentions alone are weak: a medium-to-large change in commitment (d = 0.66) produced only a small-to-medium behavior change (d = 0.33). What closes the gap is the **implementation intention** — an if-then plan specifying *when, where, how*. Gollwitzer & Sheeran (2006): d = 0.65 across 94 studies / 8,000+ participants, notable because the comparison condition already formed goal intentions. The 2024 update (Sheeran, Listrom & Gollwitzer, 642 tests) confirms the effect scales with plan format and motivational context.
 
**Decided scope (and why it's right, not a compromise):** add an *optional* if-then prompt at lock-in, **only** for the day's hardest or carried-over item — not every item, not daily-forced. This is exactly where the d=0.65 lives: implementation intentions concentrate their benefit on *problematic, slip-prone* goals, so attaching them to easy items is pure friction for little return. It also respects the system's dominant constraint — **it only works if it's used, and high daily friction kills usage** — so the long-run expected value of a low-friction, optional, hardest-item-only prompt beats a higher-friction comprehensive one. Behavior-spec change only; no schema change (lives alongside `what_shifted` or as a plan-item note).
 
On **commitment devices**, two findings shape the design. (1) The spec's **no-penalty** soft commitment is correct: hard, cost-imposing commitment devices see only ~10–30% uptake even when offered and carry backfire risk; a penalty would also feed the self-criticism loop. (2) The *social* form (the partner sees your locked plan) is the gentler, better-fitting device — its "teeth" come from social visibility and self-consistency, not stakes (see §2.7).
 
**Citations:** Gollwitzer & Sheeran (2006), *Adv. Exp. Soc. Psych.* 38:69–120; Sheeran, Listrom & Gollwitzer (2024); Rogers, Milkman & Volpp (2014), *JAMA* 311(20); commitment-demand field evidence on ~10–30% uptake.
 
---
 
### 2.4 Carry-over + gentle reassessment instead of dropping — Zeigarnik, goal disengagement/re-engagement
 
**Tag: Supports (carry-over) + adopted Modify (add genuine-abandonment path)**
 
**Carry-over** keeps incomplete items in the monitoring loop and preserves the option to convert a chronic miss into a recalibration signal rather than a silent failure. The Zeigarnik effect (uncompleted tasks stay cognitively accessible) is a plausible *soft* rationale only — its modern replication record is mixed; the load-bearing justification is the monitoring/recalibration value, not Zeigarnik.
 
**Reassessment-not-drop** is mostly correct and now gets one addition. Wrosch et al.'s goal-adjustment work shows that for *genuinely unattainable* goals the adaptive move is **disengagement + re-engagement elsewhere**, associated with higher subjective well-being and healthier cortisol patterns. The spec handles most of this well: re-anchoring a recurring goal's bar to the Floor is itself accommodative adjustment (change the goal, not the person's worth), and one-offs already offer drop. The gap was that the recurring-goal path only ever offered *lower the bar*, never *this goal is wrong for me now* — which can trap someone in low-level pursuit of a goal they'd be healthier retiring.
 
**Decided:** the recurring-goal reassessment nudge includes a **retire/redirect** option — "re-anchor the bar, **or** retire this goal and put the energy somewhere that matters more" — human-chosen, so "never auto-drop" (the system never decides) is preserved. The `paused` lifecycle state (§5) is the soft on-ramp.
 
**Citations:** Wrosch, Scheier, Miller, Schulz & Carver (2003), *PSPB* 29; Barlow et al. (2019) meta-analysis on goal adjustment & well-being. (Zeigarnik (1927) — soft rationale only.)
 
---
 
### 2.5 "Chapters" as ~5-week blocks — the fresh-start effect
 
**Tag: Supports (chapter *openings*) + adopted Modify (suppress end-countdown; carry wins across)**
 
Fresh-start applies to chapter *beginnings*: Dai, Milkman & Riis (2014) showed goal pursuit rises after temporal landmarks because they relegate past imperfections to a prior period and prompt a big-picture view. A new chapter with its own theme/start-date is a *manufactured* landmark — a good reason for chapters to exist, and a clean, non-punitive place to let a miscalibrated bar go.
 
But the same program flags two liabilities, both now addressed:
1. **Anticipated landmarks can suppress effort beforehand.** Koo, Dai et al. (2020): an upcoming landmark can *undermine* continued pursuit in the run-up (people coast toward the reset). **Decided: suppress "days left in chapter" countdowns** — emphasize the opening, not the looming close.
2. **Resetting metrics is a double-edged sword.** Dai (2018): resets help or hurt depending on prior standing. **Decided: wins surface across *all time*, not scoped per-chapter** — the chapter is a fresh *start*, never a fresh *slate that erases momentum*. (Pinned/preserved history, §6 OQ-14, already prevents the worst reset failure mode; this keeps it that way.)
~5 weeks is a reasonable soft default (long enough to show a trend, short enough for frequent fresh starts); the literature doesn't pin an optimum.
 
**Citations:** Dai, Milkman & Riis (2014), *Management Science* 60(10); Dai, Milkman & Riis (2015), *Psych. Science* 26(12); Koo, Dai, Mai & Song (2020), *OBHDP*; Dai (2018), *OBHDP* 148:12–29.
 
---
 
### 2.6 Surfacing recent wins — progress principle, competence/SDT
 
**Tag: Strongly Supports**
 
Amabile & Kramer's diary research (~12,000 entries): of all events on people's best days, the standout is simply making progress on meaningful work, and progress is self-reinforcing (real progress → more intrinsic motivation that day). Small wins punch above their weight — ~28% of incidents with only minor project impact had major impact on people's *feelings*. This is competence feedback in SDT terms, which (with autonomy and relatedness) sustains intrinsic motivation. The `win_log` (manual + derived) is the right vehicle; derived wins are especially valuable because they surface progress the person wouldn't self-credit.
 
**Decided design constraints:**
- **Tie surfaced wins to the *why*/meaning/values** the schema already stores — not to counts. This serves the progress principle, protects intrinsic motivation (§3.2), and fits the per-person framing divergence (you: wins tied to "becoming who you're trying to be"; her: wins as fuel-to-move).
- **Surface wins across all time** (§2.5), not per-chapter.
- Win-surfacing is **load-bearing, not decorative** — given the negativity asymmetry it's needed just to balance the affective ledger; treat it as a required daily element weighted to at least match the salience of any miss reflection.
- **Wins ≠ streaks.** Progress framing (you did X, it mattered) is competence-supportive; streak framing (don't break your N-day chain) is loss-aversion-driven and crowds out intrinsic motivation. Keep wins *retrospective and meaning-linked*, never chain-counting (§3.1).
**Citations:** Amabile & Kramer (2011), *The Progress Principle*; Amabile & Kramer (2007), *HBR*; Ryan & Deci (2000), *Am. Psychologist* 55(1).
 
---
 
### 2.7 Two-person shared accountability — accountability-partner & social-commitment research
 
**Tag: Supports (with an evidence-quality caveat)**
 
The direction supports shared accountability; the useful contribution is separating solid evidence from folklore.
 
**Trust this:** Harkin (2016) found progress monitoring's effect on attainment was **larger when outcomes were reported/made public**. A shared chat where each person's locked plan and morning retrospective are visible to the other is precisely "reported/public/recorded" — so the two-person design isn't just relatedness, it *strengthens the monitoring mechanism* §2.2 relies on. This is the strongest single argument for the shared-bot architecture.
 
**Don't lean on this:** the "95% with an accountability partner" (ATD) and Matthews' "+33 points" figures are weak — Matthews is non-peer-reviewed; the ATD stat is routinely garbled. Use only as illustration; the load-bearing citation is Harkin.
 
**Relatedness (SDT)** is the third leg: a shared system supplies connection alongside competence and autonomy. The spec's shared-goal handling (either completes; separate response block; not auto-suggested) makes the partnership supportive and visible without making one person's plan contingent on or dictated by the other — which protects autonomy (§2.8).
 
**Watch (now a decided guardrail):** social visibility can curdle into comparison, especially between two high-Competition achievers. Keep the partner as *witness and support, not scoreboard*; keep cross-person comparison out of surfaced views (§3.6, scheduled as future but the principle holds now).
 
**Citations:** Harkin et al. (2016), *Psych. Bulletin* 142(2); Ryan & Deci (2000); Matthews (2015, Dominican Scholar — **non-peer-reviewed**, cite with caveat).
 
---
 
### 2.8 Autonomy sensitivity (the Enneagram-8 / high-autonomy user) — SDT, reactance
 
**Tag: Supports + elevated to design objective (agency-maximizing)**
 
**Decided: autonomy-supportive (offer-not-directive) phrasing is a hard rule, and agency-maximizing is a stated design objective (§1b)** — not framing-at-the-margin. The reason it's elevated: the failure mode is not subtle. SDT: autonomously motivated people show heightened performance, wellness, and engagement vs. being told what to do (controlled motivation); controlling language shifts a person from autonomous to controlled regulation — the opposite of what the bot wants. For a high-autonomy person (Enneagram 8 prizes control, resists direction), reactance theory predicts an *active* rebound: a perceived threat to behavioral freedom motivates doing the opposite to reassert control.
 
**Design implications:**
- Codify offer-with-rationale phrasing in the tone/system layer ("here's what I'm seeing — your call"), never directives ("you should scale back").
- The **lighter-day nudge** is the highest reactance risk (the system commenting on capacity). Needs are already exempt (good); for the high-autonomy user, even a want-level nudge must read as *information she can act on*, not a recommendation.
- **Don't overcorrect into softness.** Autonomy-support ≠ absence of challenge. The 8w7 responds to being *challenged*; the Activator wants momentum. Frame stretches as a *dare she can decline* ("want to go for the stretch?"), not as a removed challenge. (This is also the natural home for the upward-recalibration offer in §4.)
**Citations:** Ryan & Deci (2000), *Am. Psychologist* 55(1); Deci & Ryan (1985); Brehm (1966), reactance theory.
 
---
 
## 3. Gaps & risks — with adoption status
 
### 3.1 Streak / loss-aversion drift — **ADOPTED as explicit non-goal**
`win_log` + daily win-surfacing can quietly mutate into streak mechanics, which run on the exact loss-aversion / self-criticism dynamics the spec is built against (breaking a streak can make people quit entirely rather than restart; "your streak is about to die" is a documented manipulation pattern). **Decided non-goal:** the bot never surfaces consecutive-day counts or loss-framed "don't break it" messaging; wins stay retrospective and meaning-linked. Carry-over-with-~1-week-berth is already the healthy "grace day" pattern — named here so a later gamification impulse can't reintroduce the report-card dynamic through the back door.
 
### 3.2 Overjustification / motivation crowding-out — **ADOPTED (intrinsic motivation as objective, §1b)**
Salient extrinsic markers can crowd out intrinsic motivation. No points/rewards (good), but heavy quantification can itself become the extrinsic frame. **Decided:** keep the *why*/meaning visible alongside numbers; treat metrics as competence feedback for the person, not as the system's scoreboard.
 
### 3.3 Genuine-abandonment case — **ADOPTED** (see §2.4): retire/redirect option added to recurring-goal reassessment.
 
### 3.4 Confidence calibration won't fix itself — **ADOPTED**
The Floor depends on a "95% sure" judgment that is itself optimistic (§2.1), and the carry-over loop is only *reactive*. **Decided:** add a light *proactive* aid at chapter-setting — surface last chapter's actual hit-rate next to each proposed bar ("you hit this ~60% of days last chapter; still a need?"). This is the outside-view prompt the planning-fallacy literature endorses, cheap given pinned history.
 
### 3.5 Negativity asymmetry is structural — **ADOPTED** (see §2.6): win-surfacing is required and weighted to at least match miss-reflection salience.
 
### 3.6 Two high-Competition achievers on one surface — **ADOPTED in principle; build = future**
Both score Competition; a shared surface risks turning support into comparison. Guardrails (shared goals not interleaved; either-completes; witness-not-scoreboard) help. **Decided:** keep cross-person comparison out of surfaced views; treat the explicit comparison-suppression *feature* work as future, but hold the principle now.
 
---
 
## 4. Decisions taken (Phase-1 close-out) + residual open question
 
These feed `doc/process/synthesis-inbox.md` → ADRs → spec update.
 
**Decided in this round:**
- **D-1 (Floor framing).** The 95% Floor is **self-efficacy calibration**: the hardest *reliably-achievable* bar, a stretch beyond current behavior but not beyond reliable capability. The **need is the performance-relevant bar** in this domain; the **want is optional reach / the next floor in waiting**. The Locke-Latham "tension" is resolved by domain + dependent-variable mismatch, not by treating needs as easy. *(rejects v0.1's "needs carry consistency, wants carry performance" framing.)*
- **D-2 (objectives added, §1b).** Add three design objectives: build self-efficacy/self-trust; maximize agency (autonomy-support as hard rule); protect intrinsic motivation (avoid crowding-out).
- **D-3 (implementation intentions).** Optional if-then (when/where/how) prompt at lock-in, scoped to the **hardest or carried-over item only**, never daily-forced. Behavior-spec only.
- **D-4 (chapters).** Suppress "days left in chapter" countdowns. Surface wins across **all time**, not per-chapter.
- **D-5 (abandonment).** Recurring-goal reassessment offers **retire/redirect**, not only lower-the-bar; human-chosen; `paused` is the soft on-ramp.
- **D-6 (anti-streak).** Explicit non-goal: no consecutive-day counts, no loss-framed nudges.
- **D-7 (wins).** Tie surfaced wins to **why/meaning/values**, not counts; required daily element; weighted ≥ miss-reflection salience.
- **D-8 (autonomy).** Offer-not-directive phrasing is a **hard rule**; agency-maximizing is an objective; lighter-day nudge framed as information for the high-autonomy user; challenges framed as decline-able dares.
- **D-9 (proactive calibration).** At chapter-setting, surface last chapter's actual hit-rate next to each proposed bar.
- **D-10 (comparison guardrail).** Keep cross-person comparison out of surfaced views; explicit suppression feature is future.
**Residual open (new, raised by the self-efficacy model):**
- **OQ-PSY-1 — Upward recalibration.** The spec's reassessment is purely *defensive* (lowers a too-high bar after ~1 week of misses). The self-efficacy model implies a missing *offensive* counterpart: a signal that detects a floor **cleared with room to spare** for N weeks and *offers* to raise it (or to promote the want to the new need). This is the mechanism that turns "become the intermediate selves one at a time" from willpower into a system behavior. It is also the natural home for the autonomy-supportive *dare* framing (D-8). **Question for you:** does this belong in MVP, and if so, what's the trigger (e.g. need cleared ≥95% of days for ≥2 weeks → offer the want as the new floor)? Left as a question, not designed, pending your call.
---
 
### Source notes
- **Strong / meta-analytic anchors:** Bandura (1977, 1997); Buehler, Griffin & Ross (1994); Locke & Latham (2002) + Klein et al. (1999); Gollwitzer & Sheeran (2006) + Sheeran et al. (2024); Harkin et al. (2016); Neff (2023); Amabile & Kramer (2011); Ryan & Deci (2000); Wrosch et al. (2003) + Barlow et al. (2019); Dai, Milkman & Riis (2014).
- **Cite with caveats:** Gail Matthews (2015) — non-peer-reviewed; ATD "95%" stat — frequently mangled, not load-bearing; Zeigarnik (1927) — soft rationale only, mixed replication; streak/gamification "backfire" — drawn from practitioner/secondary sources synthesizing Prospect Theory (Kahneman & Tversky 1979) and SDT, framed as design risk, not a quantified effect.
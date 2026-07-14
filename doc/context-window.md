# Context-window strategy — current state, paths, hurdles

> **Status:** analysis / decision-prep (not a decision). Picks up the thread [mcp-tools.md §6](product/mcp-tools.md) explicitly parks: the **width of the "thin recent slice"** and the **reset cadence**. No action needed now — this exists so the eventual choice is made deliberately, not by drift. A future ADR would formalize whichever path we take.

## 1. Current state (what's actually true today)

**The decision in force: stateless per touchpoint.** Each morning, the context handed to the LLM is **rebuilt from the database** — there is no persistent Anthropic conversation thread carried across days.

What the morning turn actually sees (per A5 `MorningContext` + A6 prompt):
- the **system prompt** — non-negotiables, the morning order, framing-at-the-margin, name-the-bar rules;
- **Tier-1 profile_doc** (curated, human-authored) — the durable "who this person is";
- **Tier-3 insight digest** (compressed, AI-maintained) — patterns, offered as hypotheses;
- **today's structured data** — the plan/candidates, yesterday's items + statuses, the win surface (derived + manual, all-time, capped), carry-overs;
- **the in-session transcript** — this morning's back-and-forth only, held in memory, keyed by chat.

It does **not** re-read the whole chat history (spec §7b). The three-tier memory carries the continuity; the raw conversation is ephemeral.

**Where the two open knobs currently sit:**
- **Width of the "thin recent slice" of raw events:** effectively **one day** (yesterday's plan/statuses/reflection via A5). Narrowest sensible setting.
- **Reset cadence:** effectively **every morning** (fully stateless). What survives a "reset" is everything that lives in the DB — Tier-1, Tier-3, goal/plan state, wins; only the ephemeral in-memory transcript is dropped.

**Token reality:** at this design the per-turn context is small — a system prompt + one day of structured plan data + a few wins + a profile excerpt. Nowhere near model limits. **There is no token pressure today.** State this plainly: the current design has no context-window *problem*; it has an open *question* about how much memory to add later, and windowing only becomes a real concern if we move toward feeding raw history.

**One thing to verify, not assume:** within a *single* day, async messages (completions logged at odd hours) append to the in-memory session transcript. That transcript is bounded by a day (reset next morning), so it can't grow unbounded — but confirm the mid-day path actually reuses/rebuilds the session as intended, and that a very chatty day doesn't balloon the in-memory transcript.

## 2. Why it might need to change (forcing functions)

None are active yet. Watch for:
1. **Cross-day conversational memory.** Stateless means the bot doesn't remember a nuance you told it yesterday *in chat* unless it was persisted as Tier-2/Tier-3. If you find yourself saying "like I mentioned yesterday…" and it has no idea, that's the signal.
2. **Growing shared chat (two-user).** A long-lived household thread accumulates; if we ever move from rebuild-from-DB toward feeding chat history, windowing bites here first.
3. **Richer within-day interaction.** If the daily loop becomes more conversational (not just morning + a couple of completions), the in-day session grows and the "how much do we keep / when do we compress" question gets real.

## 3. Potential paths (roughly in order of alignment with the design)

1. **Stay stateless (status quo).** Rebuild from DB each morning; cap/expire the in-day transcript. Cheapest, most testable (A5/A6 stay pure and reproducible), loses cross-day conversational memory. Fine as long as Tier-2/Tier-3 carry the meaning that matters.
2. **Widen the structured slice.** Inject *N* days of **structured** plan/reflection events (not raw chat) — a tunable window. Stays deterministic and bounded; gives more recent context without re-reading the chat. This is the smallest step up and the natural first move if #1 feels thin.
3. **Compaction into Tier-3.** Periodically compress recent raw events/chat into the **Tier-3 insight digest — which already exists for exactly this** — so long-run memory persists while per-turn context stays bounded. Cadence could be rolling or the ~10-week rhythm the architecture already anticipates. Best fit: it reuses an existing structure and keeps the turn small.
4. **Persistent conversation thread with windowing.** Actually keep the Anthropic message history and truncate/window it. Most "chatbot-like," most token risk, least deterministic — and it directly contradicts spec §7b ("does not re-read the whole chat"). Lowest alignment; treat as a last resort.

Likely evolution if a forcing function appears: **2 → 3**, not 4.

## 4. Hurdles & risks (what to get right before touching this)

- **⚠ Null-tolerance through the back door.** Any added "memory of recent history" must never let **silence** accumulate as evidence against the person. A summarizer that compresses "didn't respond Mon/Tue/Wed" into context has just reintroduced miss-tracking that the whole system forbids. Compaction must summarize *engaged* signal and meaning, never silence-as-failure. This is the single biggest risk.
- **Determinism vs. memory trade.** The current stateless design is highly testable (rebuild → assert exact payload). Every step toward raw persistent history trades reproducibility for recall. Preserve the ability to test the turn.
- **Tier-3 boundary (ADR-0011).** Using Tier-3 as a rolling summary is consistent *as advisory memory*, but Tier-3 → Tier-1 graduation stays human-gated. Don't let auto-compaction quietly promote itself to authoritative.
- **Reset semantics — "what survives."** Whatever the cadence, a reset may only drop **ephemeral chat**. Tier-1 (authored), Tier-3 (digest), and all goal/plan/win state must survive by construction (they're in the DB; keep it that way).
- **Cost / latency.** Daily cadence makes even a fat context cheap, but a persistent-thread approach (path 4) can balloon tokens per turn over a long-lived chat. Bound it.
- **Privacy / retention.** More persisted transcript = more personal content at rest, with backup/retention implications. Decide retention deliberately if we ever persist raw chat.

## 5. Recommendation

**No change now.** Stateless is sufficient, cheap, and the most testable — and there's no token pressure. Revisit when a real forcing function from §2 shows up (most likely: wanting within-week conversational memory, or shared-chat growth). When it does, prefer **widen-the-structured-slice → compact-into-Tier-3** over a persistent windowed thread, and write the ADR then — with the null-tolerance-in-compaction risk as the first thing it addresses.

# Future Ideas — parked, not MVP
 
Holding pen for design ideas that are wanted but deliberately out of MVP scope. An idea here is not committed; it is recorded so it isn't lost and doesn't clutter MVP docs.
 
## Periodic cross-bot profile synthesis (human-gated)
The agent observes the individual across both capabilities (task observations in task-tracker; goal observations in goal-bot). Periodically — on the order of every ~10 weeks — it can surface a digest of hypotheses about the person: "here's what I've noticed about you." For each, the human decides: is it true, how much does it matter, should it be weighted by the agent or excluded from context. Approved items graduate into the Tier-1 authored profile in the `profile` package.
 
Design constraints (so a future build doesn't drift):
- **On-demand, not automatic.** Delivered as an MCP tool the human invokes (compare profile vs. logs), not a background writer.
- **Human-gated graduation.** The agent proposes; only human approval writes to Tier-1. This is the one anticipated cross-package write into `profile`.
- **No silent rewrites.** The trust boundary from the three-tier memory model holds (ADR-0011).
Why parked: not needed for a working MVP loop; it's the mechanism that turns scattered observations into durable self-knowledge, but it presupposes both capabilities are running and producing observations. Revisit after the two capabilities work together.
 
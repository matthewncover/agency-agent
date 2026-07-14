# ADR-0017: Liveness heartbeat — an external dead-man's switch watches the system's promise to show up

**Status:** Accepted

## Context
goal-bot's core design is NULL-TOLERANCE (INV-1): an unanswered touchpoint is neutral — silence produces no tool call and nothing punitive. That is correct for the *user*, but it creates an operational blind spot for the *system*: if the bot dies, hangs, or the scheduler silently stops firing, the observable result is *no morning message* — indistinguishable from a normal quiet day. For a tool whose entire job is keeping promises, silently failing to show up is the one failure it cannot afford, and today nothing would tell us. systemd `Restart=on-failure` (B8) only catches a hard process crash, not "process alive, morning job silently not firing," and a restart is not a human alert when restarting doesn't fix things.

The principle that shapes the design: **the heartbeat watches the system's own promise — "I will show up every morning" — never the user's behavior.** It keys on whether a morning was successfully *delivered*, never on whether the user responded. It must not, even accidentally, reintroduce miss-tracking of the user.

## Options weighed

1. **External dead-man's switch** — the bot pings an external watchdog (healthchecks.io or equivalent) after each *successful* morning send; the watchdog alerts when an expected ping goes missing. Strength: it is independent of the bot's own health. If the process is wedged, the box is down, or the network is out, the *absence* of the ping is exactly what fires. A monitor that shares fate with the thing it monitors is not a monitor.
2. **systemd `WatchdogSec` + `sd_notify`** on successful job runs — catches hang/stall and restarts, but restart ≠ human alert, and it shares fate with the host: a dead box means a dead watchdog.
3. **Second local process / cron** querying the DB ("was a morning delivered in the last N hours?") and alerting — simpler than 2, but still shares fate with the host, and it now owns an alert-delivery path of its own.

**Alert-channel trap (applies to 2 and 3):** alerting through Telegram is fragile precisely when the failure *is* the Telegram send path. The alert channel must be independent of the monitored path — which option 1 gets for free by making the external watchdog own the alert.

## Decision
- **Option 1: external dead-man's switch.** Concretely: a **healthchecks.io check** (hosted free tier is sufficient for one check; self-hosted is a drop-in swap since the contract is just "GET a URL"). The watchdog owns the alert channel (email/push from healthchecks.io) — independent of Telegram, per the trap above.
- **Signal = successful scheduled morning delivery.** The scheduled morning job pings the check URL **after** `send_message` returns without error. No send, or a failed send, means no ping. The ping never keys on the user's reply — an answered morning and an ignored morning are equally healthy heartbeats.
- **The manual `/morning` debug command does not ping.** A human manually poking the bot must not mask a dead scheduler — the watchdog watches the *promise*, and the promise is the scheduled send.
- **Threshold: period 24 h, grace 2 h — alert if no successful morning send in > 26 h.** Covers the daily cadence with slack for LLM/Telegram latency and small schedule drift, while still alerting the same day a morning fails to go out.
- **One check URL for the deployment, not per person.** Any person's successful scheduled send pings it. With two users this means "both mornings dead" is what's guaranteed to fire; per-person checks (a URL map) are a straightforward later refinement if one-person-silently-broken becomes a real failure mode. Recorded as a known limit, not an accident.
- **Clean-architecture shape:** a `HeartbeatPort` in the application layer; an HTTP adapter in infrastructure pinging the configured URL; a **no-op adapter when unconfigured**, so dev and tests need no external service. A heartbeat failure is logged and swallowed — a broken watchdog must never break the morning send. Config via pydantic-settings (`HEARTBEAT_URL`); the URL is a secret (anyone holding it can feed the watchdog) and lives in the server env file, never the repo.

## Consequences
- A dead bot, a wedged process, a silently-stopped scheduler, a dead box, or a broken Telegram send path all converge on the same observable — a missed ping — and produce a human alert within ~26 h on a channel that doesn't share the failure.
- NULL-TOLERANCE is untouched, structurally: the heartbeat lives entirely in the send path (composition/telegram layer), reads nothing about plan items or outcomes, and writes nothing to the DB. User silence cannot reach it; there is no new data that could be turned into a miss-count.
- Ops gains one manual setup step (create the check, put its ping URL in `/etc/agency-agent/agency.env`) — recorded in the deploy runbook and MATTHEW-TODO/02. The friction ratchet (non-negotiable 8) is respected: zero new user-facing structure.
- The bot gains a runtime dependency on `httpx` (already present transitively via the Anthropic SDK, now declared) and one outbound HTTPS call per morning; if the watchdog is down, the only effect is a log line.
- If the deployment ever moves or multiplies, the check's period/grace and the one-URL-per-deployment choice are the two knobs to revisit.

---
name: chat-logs
description: Read goal-bot chat transcripts and tool-call logs (prod via journald on the VPS, or local stderr) for debugging, pattern review, and working the MATTHEW-TODO/03 user-testing checklist. Use whenever the user wants to show recent bot conversations, review what the bot said or logged, diagnose a mis-logged outcome, or check transcript behavior against the testing checklist.
---

# Reading goal-bot chat transcripts

The bot emits one JSON line per event on the `goal_bot.transcript` logger (stderr → journald on prod). Three event shapes, all with a UTC `ts`:

- `{"chat_id", "person_id", "direction": "in"|"out", "text", "ts"}` — a user message ("in") or bot reply ("out").
- `{"direction": "tool", "tool", "args", "ok", "error", "ts"}` — a tool call made by the LLM during a turn, with its args and whether it errored. Correlate to messages by timestamp.
- `{"direction": "usage", "model", "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "ts"}` — the API `usage` block, one line per LLM *call* (a turn with tool calls makes several calls — sum them).

Transcripts exist only from the time this feature was deployed; there is no backfill, and journald retention bounds how far back you can read.

## Consent rule (hard)

**Announce every remote command before running it** — say what you are about to run on the VPS and why, then run it. No unannounced remote exploration. (Standing rule for Matthew's VPS.)

## Prod (VPS)

The bot runs as systemd unit `goal-bot`; its stderr goes to journald. Base read:

```sh
ssh vps "journalctl -u goal-bot --since '2 days ago' -o cat" \
  | grep goal_bot.transcript | grep -o '{.*}' | jq .
```

- `-o cat` strips journald metadata, leaving the Python log line (`<asctime> goal_bot.transcript INFO {...}`); the `grep -o '{.*}'` isolates the JSON.
- Time windows: `--since '2026-08-12'`, `--since yesterday --until today`, `--since '3 hours ago'`.

Useful filters (append to the base pipe):

```sh
| jq 'select(.direction != "tool")'          # conversation only
| jq 'select(.direction == "tool")'          # tool calls only
| jq 'select(.chat_id == <id>)'              # one chat
| jq 'select(.ok == false)'                  # failed tool calls
| jq -r '"\(.ts) \(.direction): \(.text // .tool)"'   # compact timeline
```

To reconstruct a full conversation with the tool calls interleaved, drop the direction filter and sort by `ts` (lines are already chronological).

Cost for a time window (Sonnet 5 rates $2/$10 per MTok; swap rates for other models):

```sh
| jq -s 'map(select(.direction == "usage"))
  | {calls: length,
     input: (map(.input_tokens) | add),
     output: (map(.output_tokens) | add),
     cache_read: (map(.cache_read_input_tokens // 0) | add)}
  | . + {usd: (.input * 2 + .output * 10) / 1e6}'
```

For a per-day series, run the base read with `--since <day> --until <day+1>` per day. Cross-check totals against the Console usage page before drawing conclusions.

## Local dev

Transcript lines go to the running process's stderr — nothing is persisted. Run the bot in a terminal (or redirect `2>bot.log`) and read the same way.

## Notes

- `text` is private user content. Read it for debugging and pattern review only; don't quote it anywhere outside the conversation with Matthew unless asked.
- When reviewing against [MATTHEW-TODO/03-user-testing-checklist.md](../../MATTHEW-TODO/03-user-testing-checklist.md): tool lines are the ground truth for what was recorded (e.g. a `log_outcome` with the wrong `daily_plan_item_id`, a `not_done` that should never fire from silence, counter-advancing calls). Cross-check suspicious ones against the DB with the query-db skill.

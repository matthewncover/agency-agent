---
name: onboard-person
description: Add a new person (or a group/household) to goal-bot — provision the identity, wire their Telegram chat into the bot, and prepare for their first goal ingestion. Use when the user wants to add a person, onboard a partner, create a household/group, or change someone's timezone.
---

# Onboarding a person (or group) into goal-bot

Provisioning is **human-owned** (B7): Claude prepares exact commands and
verifies results; the human runs the identity-creating commands.

## 0. Verify the database target

Same rule as ingest-goals Step 0: know whether you're provisioning into dev or
prod before anything runs. For prod, the ssh tunnel (`localhost:5433`) must be
up and `.env` pointed through it.

## 1. Provision the identity — run from the Mac, not the VPS

`provision.py` is plain DB writes; with `.env` on the right target it works
from the repo checkout locally. This avoids the VPS `sudo`/`HOME`/quoting
hazards entirely. The human runs, in the repo root:

```sh
uv run python -m goal_bot.provision add-person --name <Name> --timezone <IANA tz>
# e.g. --timezone America/New_York; prints the new person_id — capture it

uv run python -m goal_bot.provision add-group --label "<Label>" --members 1,2
# only for a shared/household surface; prints the group profile id
```

Gotchas (until fixed in code):
- `Settings()` demands an integer `PERSON_ID`; if the environment has it empty,
  prefix the command with `PERSON_ID=0`.
- If running server-side anyway: use the `/usr/local/bin/goalbot` wrapper
  (`goalbot just add-person ...`) — it handles cd, env sourcing, and the
  goalbot-user switch. Avoid `just` recipes with quoted args containing `&`
  (`{{ARGS}}` re-expansion mangles them); call `python -m goal_bot.provision`
  directly instead.

## 2. Timezone

One tz per person, drives their 6:00 AM morning send. If it will change (e.g.
a move), set today's tz now and diarize the flip — it's a one-line SQL update
(`UPDATE profile.person SET timezone = '...' WHERE profile_id = N`) plus
`systemctl restart goal-bot`.

## 3. Wire Telegram (when the person actually starts)

Two surfaces exist (ADR-0020):

**Shared group chat (the normal goal surface).** The person joins the existing
group chat; identity comes from the *speaker*, never the chat:

1. Get their telegram user id: they DM `@userinfobot`, or send any message /
   `/whoami` in the group chat and read the journal's
   `auth rejected: known chat_id=..., unmapped user_id=...` line.
2. In `/etc/agency-agent/agency.env` on the VPS, add them to **both** maps
   (the chat map may repeat the same chat id; it **replaces** the single-pair
   vars when present — keep existing entries!):
   `TELEGRAM_CHAT_MAP=<groupchatid>:<pid1>,<groupchatid>:<pid2>`
   `TELEGRAM_USER_MAP=<useruid1>:<pid1>,<useruid2>:<pid2>`
3. `sudo systemctl restart goal-bot`, then check the journal's
   `chat→person map = ..., user→person map = ...` line shows everyone.

**Solo chat (legacy / special cases).** The person opens their own chat with
the bot and sends a message; get the chat id from the unknown-chat journal
line (or `getUpdates` while the bot is stopped — a running bot consumes
updates) and add the single `<chatid>:<personid>` pair to the chat map.

Unmapped speakers in a known chat are ignored, never attributed to someone
else. Scheduled mornings into a shared chat are name-labeled per person.

A person can exist and hold goals long before their Telegram wiring — goals
ingest against their person id regardless.

## 4. Chapters and goals

Chapters are per-owner: the new person needs their own chapter (and a group
needs its own) even for the same date window. Group-owned goals live in the
group's chapter and fan out to members. From here, hand off to
`/ingest-goals` with the new owner id(s).

## 5. Verify

- `SELECT * FROM profile.person` shows the new row with the right tz.
- After Telegram wiring: the person sends `/morning` and gets their own plan
  (not another member's).
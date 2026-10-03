# Deploy runbook (B8 — VPS)

Ops for running goal-bot on the VPS against a real Postgres. Per spec
[B8-vps-deploy.md](../doc/build/B8-vps-deploy.md) and the CLAUDE.md boundaries,
**you** run the deploy, migrations, and secrets — the agent only authors these
files. Nothing here auto-applies migrations or commits secrets.

**Decisions baked in:** Telegram **polling**, prod on the VPS's own Postgres 16,
local Docker stays dev/test only. The original posture (no public URL, no TLS,
no inbound port) changed in [ADR-0021](../doc/adr/0021-public-https-miniapp.md):
the morning checklist serves a Telegram Mini App over HTTPS behind Caddy.

**Current state:** the VPS checkout tracks the `v2` branch (`main` is frozen at
tag `v1-final`). The `routines` unit is the live service; goal-bot (v1) is
stopped and disabled.

Artifacts in this dir:

| file | what |
|------|------|
| `goal-bot.service` | systemd unit for the goal-bot polling bot (v1; stopped and disabled) |
| `routines.service` | systemd unit for the morning checklist bot + Mini App server (127.0.0.1:8081) |
| `Caddyfile` | public HTTPS front door for `trendingupward.space`, path-routed to localhost apps |
| `deploy.sh` | routine one-command deploy: pull → sync → migration gate → restart → health check (C2) |
| `backup.sh` | daily `pg_dump` + prune + optional offsite copy |
| `restore.sh` | restore a dump (also used to verify a backup) |
| `../.env.prod.example` | prod env template (fill on the server, never commit) |
| `just deploy-migrate` | print migration plan, apply only on backup confirm + typed confirm |

## Routine deploy (C2 — after first deploy)

Ship a change already pushed to a **green** `v2` (CI is the gate; the script
doesn't check GitHub, so deploying from red is on you):

```sh
ssh vps '/opt/agency-agent/deploy/deploy.sh'
# or on the box: cd /opt/agency-agent && just deploy
```

`just deploy` restarts the `routines` unit by default (`UNIT=routines`);
`just deploy goal-bot` would target the stopped v1 unit.

The script (as root; repo steps drop to `goalbot`): `git pull --ff-only` →
`uv sync --locked --all-packages` → **stop if migrations are pending** →
`systemctl restart $UNIT` → health check (unit active + startup marker in
the journal, else non-zero exit with the journal tail). It never applies a
migration and never force-pulls.

**When it stops on pending migrations** (in this order — the backup is the
restore point for the schema change):

```sh
set -a; . /etc/agency-agent/agency.env; set +a
deploy/backup.sh          # 1. restore point
just deploy-migrate       # 2. review plan; confirms backup, then typed 'upgrade'
just deploy               # 3. re-run the routine deploy
```

**Rollback:** code-only → as `goalbot`, `git checkout <prev-sha>` in
`/opt/agency-agent`, re-run `deploy/deploy.sh`, then `git switch v2` once
fixed. A migrated deploy rolls back via `restore.sh` from the pre-migration
backup — which is why the backup step is mandatory, not documentation.

## First deploy (fresh VPS)

1. **Provision Postgres 16** on the VPS (package or container + persistent
   volume). Create the app role/db:
   ```sql
   CREATE ROLE goalbot LOGIN PASSWORD '...';
   CREATE DATABASE agency OWNER goalbot;
   ```

2. **Get the code** — `sudo git clone <repo> /opt/agency-agent`, then a
   dedicated user owns it:
   ```sh
   sudo useradd --system --home /opt/agency-agent --shell /usr/sbin/nologin goalbot
   sudo chown -R goalbot:goalbot /opt/agency-agent
   ```
   Install `uv` (`command -v uv` → adjust `ExecStart` in the unit if not
   `/usr/local/bin/uv`). `uv run` will build the workspace venv on first start.

3. **Secrets** — outside the repo, locked down:
   ```sh
   sudo mkdir -p /etc/agency-agent
   sudo install -m 0640 -o goalbot -g goalbot \
     /opt/agency-agent/.env.prod.example /etc/agency-agent/agency.env
   sudo -u goalbot $EDITOR /etc/agency-agent/agency.env   # fill real values
   ```
   Confirm `git status` in the repo is clean — no env file tracked.

4. **Migrations (human-applied, reviewed)** — from `/opt/agency-agent` with the
   prod `DATABASE_URL` exported:
   ```sh
   set -a; . /etc/agency-agent/agency.env; set +a
   just deploy-migrate
   ```
   This prints target DB, `alembic current`, `alembic history`, and the offline
   `alembic upgrade --sql head` plan, then applies `alembic upgrade head` **only**
   after you type `upgrade`. The agent never runs this against the live DB.

5. **Start under supervision:**
   ```sh
   sudo cp deploy/goal-bot.service /etc/systemd/system/goal-bot.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now goal-bot.service
   journalctl -u goal-bot -f
   ```
   A scheduled `/morning` should reach your real bot.

   (This is the v1 goal-bot unit. On v2, install `routines.service` instead;
   see § Morning checklist (routines).)

## Reboot survival (acceptance #2)

`enable`d + `Restart=on-failure` → the bot returns after a reboot. Verify:
`sudo reboot`, then `systemctl is-active goal-bot` once back.

## Backups (acceptance #3)

Install the cron (as goalbot), pointing at the same env:
```sh
# crontab -u goalbot -e
15 3 * * * set -a; . /etc/agency-agent/agency.env; set +a; \
  BACKUP_REMOTE=gdrive:goal-bot-backups /opt/agency-agent/deploy/backup.sh \
  >> /var/log/goal-bot-backup.log 2>&1
```
**Verify a restore once** (don't trust an untested backup):
```sh
createdb agency_restore_test
RESTORE_URL=postgresql://goalbot:...@localhost:5432/agency_restore_test \
  deploy/restore.sh /var/backups/goal-bot/agency-<ts>.dump
# eyeball row counts, then dropdb agency_restore_test
```

## Liveness heartbeat (ADR-0017)

A dead bot looks exactly like a quiet day (null-tolerance), so an **external
dead-man's switch** watches the system's promise to show up: the bot GETs
`HEARTBEAT_URL` after each successful **scheduled** morning send, and the
external watchdog alerts a human when the expected ping goes missing. The
monitor deliberately lives off-box and alerts off-Telegram — it must not share
fate with what it watches. Unset `HEARTBEAT_URL` ⇒ no-op (dev/tests).

Manual setup (once):

1. Create a check at [healthchecks.io](https://healthchecks.io) (free tier;
   self-hosted works identically): **Period = 1 day, Grace = 2 hours** — alert
   if no successful morning send in > 26 h.
2. Set the check's alert channel to email/push (something that is **not**
   Telegram).
3. Put the check's ping URL in `/etc/agency-agent/agency.env` as
   `HEARTBEAT_URL=...`. The URL is a secret — never commit it.
4. `sudo systemctl restart goal-bot`, then after the next scheduled morning,
   confirm the check shows a fresh ping.

One check covers the deployment: any person's successful scheduled send pings
it (per-person checks are a later refinement, see ADR-0017). The `/morning`
debug command intentionally does **not** ping — manual pokes must not mask a
dead scheduler.

## Morning checklist (routines)

A separate Telegram bot and process (ADR-0021). Each morning it posts one
message to the shared group chat with a button that opens the Mini App at
`https://trendingupward.space/morning/`. One process (`python -m routines`)
runs Telegram polling, the aiohttp Mini App server on `127.0.0.1:8081`, and the
scheduler. Caddy is the only public listener and strips the `/morning` prefix
before proxying. Identity comes from Telegram's signed Mini App initData, mapped
to persons via `TELEGRAM_USER_MAP`.

First-time setup (once, in this order):

1. **Domain.** A record `@` → the VPS IP (done). Turn **auto-renew on** at
   Namecheap: a lapsed domain takes the Mini App down with it.
2. **BotFather.** Create the new bot (`/newbot`), then `/newapp` for it with
   short name `morning` and URL `https://trendingupward.space/morning/`. Add the
   bot to the group chat. Privacy mode can stay on: the bot only needs
   `/morning`.
3. **Firewall.** Check `sudo ufw status` on the box and any Vultr firewall
   group in the Vultr dashboard. Allow `80/tcp` (ACME challenge + redirect) and
   `443/tcp`:
   ```sh
   sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
   ```
4. **Caddy.** Install from its official apt repo
   ([instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)),
   then:
   ```sh
   sudo cp /opt/agency-agent/deploy/Caddyfile /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```
   Caddy fetches and renews the Let's Encrypt cert on its own.
5. **Switch the checkout to v2** (`main` is frozen at tag `v1-final`):
   ```sh
   sudo -u goalbot git -C /opt/agency-agent fetch
   sudo -u goalbot git -C /opt/agency-agent switch v2
   ```
6. **Migration 0010** (human-gated, backup first):
   ```sh
   cd /opt/agency-agent
   set -a; . /etc/agency-agent/agency.env; set +a
   deploy/backup.sh
   just deploy-migrate
   ```
7. **Env.** Add the `ROUTINES_*` vars to `/etc/agency-agent/agency.env` (see
   `.env.prod.example` § Morning checklist) and make sure `TELEGRAM_USER_MAP`
   is set. Paste the bot token by hand on the box, never into chat or AI tools.
   Never set `ROUTINES_DEV_PERSON_ID` in prod.
8. **Install the unit, then deploy.** `just deploy` runs `uv sync
   --all-packages` (the checkout just gained the `routines` package), checks
   no migration is pending, starts the unit, and health-checks it:
   ```sh
   sudo cp /opt/agency-agent/deploy/routines.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable routines
   cd /opt/agency-agent && just deploy
   journalctl -u routines -f
   ```
9. **Confirm the group chat id.** Send `/morning` in the group;
   `journalctl -u routines` logs the calling chat id. Compare it to
   `ROUTINES_CHAT_ID` (fix the env file and `sudo systemctl restart routines`
   if they differ).
10. **Heartbeat.** Reuse the existing healthchecks.io check (`HEARTBEAT_URL`,
    same Liveness heartbeat setup above): routines pings it after the
    scheduled morning send. Unpause the check once the first scheduled send
    has gone out.
11. **Smoke test.** `curl -I https://trendingupward.space/morning/` returns
    `200`. Open the Mini App from the button in Telegram; Matthew and Jade
    each see their own list.

After setup, routine deploys are `just deploy` (defaults to the `routines`
unit). goal-bot (v1) stays stopped and disabled; its unit file remains in
the repo for reference.

## Data going live (one-way)

Decide once: seed prod fresh via real ingestion, or migrate dev data in. Never
point tests at prod (same rule as A1). Going live is a one-way data step.

## Later / out of scope

Webhooks (a public HTTPS URL now exists per ADR-0021, but both bots still
poll; not adopted), HA/multi-region, container orchestration,
push-based/auto CD (routine deploys are one human-triggered command — C2).
Migrations stay human-gated on purpose.

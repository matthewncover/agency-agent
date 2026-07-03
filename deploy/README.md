# Deploy runbook (B8 — VPS)

Ops for running goal-bot on the VPS against a real Postgres. Per spec
[B8-vps-deploy.md](../doc/build/B8-vps-deploy.md) and the CLAUDE.md boundaries,
**you** run the deploy, migrations, and secrets — the agent only authors these
files. Nothing here auto-applies migrations or commits secrets.

**Decisions baked in:** Telegram **polling** (simplest for one user; no public
URL/TLS), prod on the VPS's own Postgres 16, local Docker stays dev/test only.

Artifacts in this dir:

| file | what |
|------|------|
| `goal-bot.service` | systemd unit for the polling bot |
| `backup.sh` | daily `pg_dump` + prune + optional offsite copy |
| `restore.sh` | restore a dump (also used to verify a backup) |
| `../.env.prod.example` | prod env template (fill on the server, never commit) |
| `just deploy-migrate` | print migration plan, apply only on typed confirm |

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

## Data going live (one-way)

Decide once: seed prod fresh via real ingestion, or migrate dev data in. Never
point tests at prod (same rule as A1). Going live is a one-way data step.

## Later / out of scope

Webhook (needs public URL + TLS), HA/multi-region, container orchestration, CD.
Migrations stay human-gated on purpose.

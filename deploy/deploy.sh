#!/usr/bin/env bash
# deploy.sh — routine one-command deploy on the VPS (C2).
#
# Usage (as root on the VPS, from anywhere):
#   /opt/agency-agent/deploy/deploy.sh        # or: cd /opt/agency-agent && just deploy
#
# What it does, in order:
#   1. git pull --ff-only        (as goalbot; refuses non-fast-forward)
#   2. uv sync --locked --all-packages
#   3. pending-migration check   (alembic current vs heads; STOPS if they differ —
#                                 migrations stay human-gated via `just deploy-migrate`)
#   4. systemctl restart goal-bot
#   5. health check              (unit active + startup marker in the journal)
#
# This script never applies a migration and never force-pulls. Deploy only
# from a green CI run on main. Code-only rollback: as goalbot,
# `git checkout <prev-sha>` in the repo, then re-run this script.
#
# Config via env:
#   REPO_DIR   repo checkout            (default: /opt/agency-agent)
#   APP_USER   repo owner / service user (default: goalbot)
#   UNIT       systemd unit             (default: goal-bot)
#   ENV_FILE   secrets file             (default: /etc/agency-agent/agency.env)
#   HEALTH_TIMEOUT  seconds to wait for the startup marker (default: 90)
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/agency-agent}"
APP_USER="${APP_USER:-goalbot}"
UNIT="${UNIT:-goal-bot}"
ENV_FILE="${ENV_FILE:-/etc/agency-agent/agency.env}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

if [[ $EUID -ne 0 ]]; then
  echo "[deploy] must run as root (restarts ${UNIT} and drops to ${APP_USER} for repo steps)" >&2
  exit 1
fi

# DATABASE_URL for the alembic check comes from the same env file the service
# uses; never from the repo.
if [[ -z "${DATABASE_URL:-}" ]]; then
  [[ -r "$ENV_FILE" ]] || { echo "[deploy] $ENV_FILE not readable and DATABASE_URL unset" >&2; exit 1; }
  set -a; . "$ENV_FILE"; set +a
fi

# Repo-touching steps run as the app user so root never owns files in the
# checkout. Share the service's uv cache (see goal-bot.service).
as_app() {
  sudo -u "$APP_USER" \
    env UV_CACHE_DIR=/var/cache/goal-bot-uv DATABASE_URL="$DATABASE_URL" \
    "$@"
}

cd "$REPO_DIR"

echo "[deploy] 1/5 git pull --ff-only"
before="$(as_app git rev-parse --short HEAD)"
as_app git pull --ff-only
after="$(as_app git rev-parse --short HEAD)"
echo "[deploy]      ${before} -> ${after}"

echo "[deploy] 2/5 uv sync --locked --all-packages"
as_app uv sync --locked --all-packages

echo "[deploy] 3/5 migration check"
current="$(as_app uv run alembic current 2>/dev/null | awk 'NF {print $1; exit}')"
head_rev="$(as_app uv run alembic heads 2>/dev/null | awk 'NF {print $1; exit}')"
if [[ "$current" != "$head_rev" ]]; then
  cat >&2 <<EOF
[deploy] STOP: pending migration(s) — db at '${current:-<none>}', code head is '${head_rev}'.
[deploy] Nothing was restarted. To proceed (human-gated, in this order):
[deploy]   1. backup:   deploy/backup.sh        (restore point before schema change)
[deploy]   2. migrate:  just deploy-migrate     (review plan, typed confirm)
[deploy]   3. re-run:   deploy/deploy.sh
EOF
  exit 2
fi
echo "[deploy]      db at head (${current})"

echo "[deploy] 4/5 systemctl restart ${UNIT}"
restart_ts="$(date '+%Y-%m-%d %H:%M:%S')"
systemctl restart "$UNIT"

echo "[deploy] 5/5 health check (up to ${HEALTH_TIMEOUT}s)"
# Healthy = unit active AND the bot logged its startup marker since restart.
# Markers: "run: starting run_polling" (composition.run) or PTB's
# "Application started" once polling is actually up.
deadline=$((SECONDS + HEALTH_TIMEOUT))
while ((SECONDS < deadline)); do
  if ! systemctl is-active --quiet "$UNIT"; then
    sleep 2
    continue
  fi
  if journalctl -u "$UNIT" --since "$restart_ts" --no-pager 2>/dev/null |
    grep -qE "run: starting run_polling|Application started"; then
    echo "[deploy] OK: ${UNIT} active, startup marker seen (now at ${after})"
    exit 0
  fi
  sleep 2
done

echo "[deploy] FAILED: no healthy startup within ${HEALTH_TIMEOUT}s — journal tail:" >&2
systemctl status "$UNIT" --no-pager >&2 || true
journalctl -u "$UNIT" --since "$restart_ts" -n 40 --no-pager >&2 || true
exit 1

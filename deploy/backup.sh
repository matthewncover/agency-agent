#!/usr/bin/env bash
# backup.sh — pg_dump the prod DB, prune old dumps, optionally copy offsite (B8).
#
# A personal tool still deserves not losing the promise-history.
#
# Cron (as the goalbot user), daily at 03:15:
#   15 3 * * * /opt/agency-agent/deploy/backup.sh >> /var/log/goal-bot-backup.log 2>&1
#
# Config via env (inherit the app's EnvironmentFile, or set here):
#   DATABASE_URL   required — same URL the app uses
#   BACKUP_DIR     local dump dir           (default: /var/backups/goal-bot)
#   BACKUP_KEEP    dumps to retain          (default: 14)
#   BACKUP_REMOTE  optional rclone remote   (e.g. "gdrive:goal-bot-backups")
set -euo pipefail

DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/goal-bot}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/agency-${ts}.dump"

mkdir -p "$BACKUP_DIR"

# Custom format (-Fc): compressed, restorable with pg_restore, portable.
echo "[backup] dumping -> ${out}"
pg_dump --dbname="$DATABASE_URL" --format=custom --file="$out"

# Integrity smoke check: pg_restore can read the archive TOC.
pg_restore --list "$out" >/dev/null
echo "[backup] ok: $(du -h "$out" | cut -f1)"

# Prune: keep the newest $BACKUP_KEEP dumps.
mapfile -t old < <(ls -1t "${BACKUP_DIR}"/agency-*.dump 2>/dev/null | tail -n +"$((BACKUP_KEEP + 1))")
if ((${#old[@]})); then
  echo "[backup] pruning ${#old[@]} old dump(s)"
  rm -f "${old[@]}"
fi

# Offsite copy (optional). rclone keeps it dead simple; any remote works.
if [[ -n "$BACKUP_REMOTE" ]]; then
  echo "[backup] copying offsite -> ${BACKUP_REMOTE}"
  rclone copy "$out" "$BACKUP_REMOTE"
fi

echo "[backup] done"

#!/usr/bin/env bash
# restore.sh — restore a pg_dump custom-format archive into a target DB (B8).
#
# DESTRUCTIVE: this DROPs and recreates objects in the target DB (pg_restore
# --clean --if-exists). Stop the bot first and be certain of the target URL.
#
#   sudo systemctl stop goal-bot
#   RESTORE_URL=postgresql://goalbot:...@localhost:5432/agency \
#     deploy/restore.sh /var/backups/goal-bot/agency-20260702T031500Z.dump
#   sudo systemctl start goal-bot
#
# Verify a restore at least once (B8 acceptance #3): restore into a throwaway
# DB and eyeball row counts before you ever trust it against prod.
#   createdb agency_restore_test
#   RESTORE_URL=postgresql://goalbot:...@localhost:5432/agency_restore_test \
#     deploy/restore.sh <dump>
set -euo pipefail

dump="${1:?usage: restore.sh <dump-file>}"
RESTORE_URL="${RESTORE_URL:?RESTORE_URL must be set (the TARGET db — not necessarily prod)}"

[[ -f "$dump" ]] || { echo "no such dump: $dump" >&2; exit 1; }

echo "[restore] target: ${RESTORE_URL%%\?*}"
echo "[restore] source: ${dump}"
read -r -p "This will DROP and recreate objects in the target. Type 'restore' to proceed: " ok
[[ "$ok" == "restore" ]] || { echo "aborted"; exit 1; }

pg_restore \
  --dbname="$RESTORE_URL" \
  --clean --if-exists \
  --no-owner --no-privileges \
  --exit-on-error \
  "$dump"

echo "[restore] done — verify row counts before trusting this DB"

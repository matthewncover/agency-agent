up:
    docker compose up -d --wait

down:
    docker compose down

test:
    uv run pytest

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

# Seed the toy dataset (real first chapter + coverage goals) under a fresh person.
seed:
    uv run python -m goal_bot.seed

# Wipe-and-retry loop: rebuild both schemas clean, then seed the toy dataset (person_id=1).
toy-reset: reset-db seed

# Create just your person profile (the ingestion owner id) — no demo goals.
seed-me:
    uv run python -m goal_bot.seed --person-only

# B7: provision an identity (human-owned). e.g. `just add-person --name Ada --timezone America/New_York`
add-person *ARGS:
    uv run python -m goal_bot.provision add-person {{ARGS}}

# B7: provision a household group. e.g. `just add-group --label "Ada & Bo" --members 1,2`
add-group *ARGS:
    uv run python -m goal_bot.provision add-group {{ARGS}}

# Wipe seeded/toy goal data (chapters, goals, versions, plans, items, wins…) but KEEP your person/profile.
wipe-goals:
    docker compose exec -T postgres psql -U agency -d agency -c "TRUNCATE goalbot.chapter, goalbot.goal, goalbot.goal_version, goalbot.goal_state, goalbot.daily_plan, goalbot.daily_plan_item, goalbot.win_log, goalbot.friction_log, goalbot.insight, goalbot.tag, goalbot.goal_tag, goalbot.anticipated_obstacle RESTART IDENTITY CASCADE;"

# Nuclear: drop & rebuild BOTH schemas via Alembic (also removes your person — re-create it after).
reset-db:
    uv run alembic downgrade base && uv run alembic upgrade head

run:
    uv run python -m goal_bot

db-url:
    @echo $DATABASE_URL

# C2: routine deploy on the VPS — ff-pull, sync, migration-pending gate,
# restart, health check. Stops (without restarting) if migrations are pending
# and hands you to `deploy-migrate`. Run as root on the VPS.
deploy:
    deploy/deploy.sh

# B8: preview the pending migration plan against $DATABASE_URL, then apply it
# only after an explicit typed confirm. Human-run, never auto-run (CLAUDE.md).
# Point $DATABASE_URL at prod in the deploy shell, review, then confirm.
# C2: a schema change needs a restore point first — confirm a fresh backup.
deploy-migrate:
    @echo "== target DB ==" && echo "${DATABASE_URL%%\\?*}"
    @echo "\n== current revision ==" && uv run alembic current
    @echo "\n== history ==" && uv run alembic history --verbose
    @echo "\n== offline SQL preview (current -> head) ==" && uv run alembic upgrade --sql head
    @printf "\nFresh backup taken (deploy/backup.sh)? Type 'backup-done' to continue: " && \
      read bak && [ "$bak" = "backup-done" ] || \
      { echo "aborted — run deploy/backup.sh first (restore point before schema change)"; exit 1; }
    @printf "\nApply 'alembic upgrade head' to the DB above? Type 'upgrade' to proceed: " && \
      read ans && [ "$ans" = "upgrade" ] && uv run alembic upgrade head || \
      echo "aborted — no migration applied"

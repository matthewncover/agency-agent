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

seed:
    uv run python -m goal_bot.seed

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

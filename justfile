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

run:
    uv run python -m goal_bot

db-url:
    @echo $DATABASE_URL

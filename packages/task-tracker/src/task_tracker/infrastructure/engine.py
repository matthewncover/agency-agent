import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine

DEFAULT_DATABASE_URL = "postgresql://agency:agency@localhost:5432/agency"


class _EnvSettings(BaseSettings):
    """DATABASE_URL from the environment, falling back to a `.env` file in the
    working directory — same convention as goal_bot.config, so every launcher
    (Claude Code .mcp.json, Claude Desktop, systemd) resolves it identically."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL


def normalize_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def make_engine(database_url: str) -> Engine:
    return create_engine(normalize_url(database_url), future=True)


def default_engine() -> Engine:
    return make_engine(_EnvSettings().database_url)


def default_owner_id() -> int:
    """The person whose tasks this process reads/writes. Single-user MVP:
    `TASKTRACKER_OWNER_ID` wins, then `PERSON_ID` (shared with goal-bot), else 1."""
    return int(
        os.environ.get("TASKTRACKER_OWNER_ID") or os.environ.get("PERSON_ID") or 1
    )

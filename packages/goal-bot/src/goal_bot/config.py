from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://agency:agency@localhost:5432/agency"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0
    person_id: int = 0
    debug_morning_interval: int = 0  # seconds; 0 = use cron at person's local time
    morning_time: str = ""  # HH:MM override; "" = use person.morning_prompt_local_time


def get_settings() -> Settings:
    return Settings()

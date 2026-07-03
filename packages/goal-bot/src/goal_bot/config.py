from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://agency:agency@localhost:5432/agency"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0
    person_id: int = 0
    # Multi-person mapping (B7): "chatid:personid,chatid:personid". When set it
    # takes precedence; otherwise the single telegram_chat_id/person_id pair is
    # used (back-compat with the A7 single-user config).
    telegram_chat_map: str = ""
    debug_morning_interval: int = 0  # seconds; 0 = use cron at person's local time
    morning_time: str = ""  # HH:MM override; "" = use person.morning_prompt_local_time

    def chat_person_pairs(self) -> list[tuple[int, int]]:
        """Resolved (chat_id, person_id) pairs. Parses telegram_chat_map if set,
        else falls back to the single legacy pair (if configured)."""
        if self.telegram_chat_map.strip():
            pairs: list[tuple[int, int]] = []
            for entry in self.telegram_chat_map.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                chat_s, person_s = entry.split(":")
                pairs.append((int(chat_s), int(person_s)))
            return pairs
        if self.telegram_chat_id and self.person_id:
            return [(self.telegram_chat_id, self.person_id)]
        return []


def get_settings() -> Settings:
    return Settings()

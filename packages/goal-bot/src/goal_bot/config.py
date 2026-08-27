from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://agency:agency@localhost:5432/agency"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    # Sonnet 5 runs adaptive thinking by default; effort controls how much it
    # thinks/spends per turn. "medium" ≈ Sonnet 4.6 at its old default.
    anthropic_effort: str = "medium"
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0
    person_id: int = 0
    # Multi-person mapping (B7): "chatid:personid,chatid:personid". When set it
    # takes precedence; otherwise the single telegram_chat_id/person_id pair is
    # used (back-compat with the A7 single-user config). The same chat id may
    # appear for several persons — that chat is a shared surface (B8) and
    # requires telegram_user_map to tell speakers apart.
    telegram_chat_map: str = ""
    # Shared-chat speaker identity (B8): "telegramuserid:personid,...". When
    # set, the acting person is resolved from who sent the message; the chat
    # map then only defines which chats the bot lives in and where each
    # person's scheduled sends go. A speaker missing from this map is ignored,
    # never attributed to another person.
    telegram_user_map: str = ""
    debug_morning_interval: int = 0  # seconds; 0 = use cron at person's local time
    morning_time: str = ""  # HH:MM override; "" = use person.morning_prompt_local_time
    # Liveness (ADR-0017): external dead-man's-switch ping URL (e.g. a
    # healthchecks.io check), pinged after each successful scheduled morning
    # send. Empty = no-op heartbeat (dev/tests need no external service).
    heartbeat_url: str = ""
    heartbeat_timeout: float = 10.0  # seconds; HTTP timeout for the ping

    def chat_person_pairs(self) -> list[tuple[int, int]]:
        """Resolved (chat_id, person_id) pairs. Parses telegram_chat_map if set,
        else falls back to the single legacy pair (if configured)."""
        if self.telegram_chat_map.strip():
            return _parse_id_pairs(self.telegram_chat_map)
        if self.telegram_chat_id and self.person_id:
            return [(self.telegram_chat_id, self.person_id)]
        return []

    def user_person_pairs(self) -> list[tuple[int, int]]:
        """Resolved (telegram_user_id, person_id) pairs from telegram_user_map;
        empty when speaker routing is unconfigured (legacy chat routing)."""
        return _parse_id_pairs(self.telegram_user_map)


def _parse_id_pairs(raw: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        left, right = entry.split(":")
        pairs.append((int(left), int(right)))
    return pairs


def get_settings() -> Settings:
    return Settings()

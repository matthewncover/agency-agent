from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Settings(BaseSettings):
    """Read from the same env file as goal-bot. DATABASE_URL, HEARTBEAT_URL
    and TELEGRAM_USER_MAP are shared; everything else is ROUTINES_*."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://agency:agency@localhost:5432/agency"
    heartbeat_url: str = ""
    heartbeat_timeout: float = 10.0
    # "telegramuserid:personid,..." (ADR-0020). Whoever opens the Mini App is
    # resolved through this map; an unmapped Telegram user sees "not set up".
    telegram_user_map: str = ""

    routines_bot_token: str = ""
    routines_bot_username: str = ""  # without the @
    routines_miniapp_short_name: str = "morning"  # BotFather /newapp short name
    routines_chat_id: int = 0  # the group the daily and completion messages go to
    routines_morning_time: str = "06:00"  # HH:MM, in routines_tz
    routines_tz: str = "America/Los_Angeles"
    routines_http_host: str = "127.0.0.1"
    routines_http_port: int = 8081
    # Dev only: serve every request as this person, skipping Telegram auth.
    # Refused unless the server binds a loopback host. Never set in prod.
    routines_dev_person_id: int = 0
    # "personid:pronoun,..." for "completed his/her morning routine".
    routines_possessive: str = ""

    def user_person(self) -> dict[int, int]:
        return {int(k): int(v) for k, v in _parse_pairs(self.telegram_user_map)}

    def possessive(self) -> dict[int, str]:
        return {int(k): v for k, v in _parse_pairs(self.routines_possessive)}

    def morning_time(self) -> time:
        return time.fromisoformat(self.routines_morning_time)

    def miniapp_link(self) -> str:
        return (
            f"https://t.me/{self.routines_bot_username}/"
            f"{self.routines_miniapp_short_name}"
        )

    def check(self) -> None:
        """Fail fast on settings that would make the process unsafe or useless."""
        if (
            self.routines_dev_person_id
            and self.routines_http_host not in LOOPBACK_HOSTS
        ):
            raise SystemExit(
                "ROUTINES_DEV_PERSON_ID skips auth; refusing to bind "
                f"{self.routines_http_host}. Use 127.0.0.1."
            )
        if not self.routines_bot_token and not self.routines_dev_person_id:
            raise SystemExit("ROUTINES_BOT_TOKEN is not set")
        if self.routines_bot_token and not (
            self.routines_bot_username and self.routines_chat_id
        ):
            raise SystemExit(
                "ROUTINES_BOT_USERNAME and ROUTINES_CHAT_ID are required with a bot"
            )


def _parse_pairs(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        left, right = entry.split(":")
        pairs.append((left.strip(), right.strip()))
    return pairs


def get_settings() -> Settings:
    return Settings()

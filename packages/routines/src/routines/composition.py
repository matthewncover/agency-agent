import logging

from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from agency_profile.infrastructure.engine import make_engine
from aiohttp import web

from routines.application.checklist_service import ChecklistService
from routines.application.ports import HeartbeatPort, NoopHeartbeat
from routines.config import Settings, get_settings
from routines.infrastructure.checklist_repo import SqlAlchemyChecklistRepository
from routines.infrastructure.heartbeat import HttpHeartbeat
from routines.infrastructure.telegram_bot import RoutinesBot
from routines.web.server import Authenticator, build_web_app

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logging.getLogger("routines").setLevel(logging.INFO)
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
_log = logging.getLogger(__name__)


def build_heartbeat(settings: Settings) -> HeartbeatPort:
    url = settings.heartbeat_url.strip()
    if url:
        return HttpHeartbeat(url, timeout=settings.heartbeat_timeout)
    return NoopHeartbeat()


def build_service(settings: Settings) -> ChecklistService:
    engine = make_engine(settings.database_url)
    return ChecklistService(
        repo=SqlAlchemyChecklistRepository(engine),
        profiles=SqlAlchemyProfileRepository(engine),
        possessive=settings.possessive(),
    )


def build_authenticator(settings: Settings) -> Authenticator:
    if settings.routines_dev_person_id:
        _log.warning(
            "DEV MODE: Telegram auth is off; every request is person %s",
            settings.routines_dev_person_id,
        )
    return Authenticator(
        bot_token=settings.routines_bot_token,
        user_person=settings.user_person(),
        dev_person_id=settings.routines_dev_person_id or None,
    )


def run_web_only(settings: Settings) -> None:
    """Dev without a bot token: just the page and API, and completion
    messages go to the log instead of Telegram."""

    async def log_notify(text: str) -> None:
        _log.info("completion message (not sent, no bot):\n%s", text)

    app = build_web_app(
        build_service(settings), build_authenticator(settings), log_notify
    )
    web.run_app(app, host=settings.routines_http_host, port=settings.routines_http_port)


def run() -> None:
    settings = get_settings()
    settings.check()
    if not settings.routines_bot_token:
        run_web_only(settings)
        return

    bot: RoutinesBot | None = None

    async def notify(text: str) -> None:
        assert bot is not None
        await bot.notify(text)

    bot = RoutinesBot(
        token=settings.routines_bot_token,
        chat_id=settings.routines_chat_id,
        miniapp_link=settings.miniapp_link(),
        heartbeat=build_heartbeat(settings),
        web_app=build_web_app(
            build_service(settings), build_authenticator(settings), notify
        ),
        http_host=settings.routines_http_host,
        http_port=settings.routines_http_port,
    )
    bot.schedule_morning(settings.morning_time(), settings.routines_tz)
    _log.info(
        "run: morning message at %s %s to chat %s",
        settings.routines_morning_time,
        settings.routines_tz,
        settings.routines_chat_id,
    )
    # deploy.sh's health check greps for this exact line.
    _log.info("run: starting run_polling")
    bot.run_polling()

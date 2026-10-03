import logging
from datetime import time

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from routines.application.ports import HeartbeatPort

_log = logging.getLogger(__name__)

MORNING_TEXT = "Good morning."
BUTTON_TEXT = "Open morning checklist"
MISFIRE_GRACE_SECONDS = 3600


def morning_markup(miniapp_link: str) -> InlineKeyboardMarkup:
    # A url button to the Mini App's direct link: web_app buttons only work in
    # private chats, and the direct link still hands the page signed initData.
    return InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_TEXT, url=miniapp_link)]])


class RoutinesBot:
    """The Telegram side: one shared morning message a day, `/morning` on
    demand, and the completion posts the web API asks for. PTB owns the event
    loop, so the scheduler and the web server start in its post_init."""

    def __init__(
        self,
        token: str,
        chat_id: int,
        miniapp_link: str,
        heartbeat: HeartbeatPort,
        web_app: web.Application,
        http_host: str,
        http_port: int,
    ) -> None:
        self._chat_id = chat_id
        self._markup = morning_markup(miniapp_link)
        self._heartbeat = heartbeat
        self._web_app = web_app
        self._http_host = http_host
        self._http_port = http_port
        self._runner: web.AppRunner | None = None
        self.scheduler = AsyncIOScheduler()

        self._app = (
            Application.builder()
            .token(token)
            .post_init(self._start)
            .post_shutdown(self._stop)
            .build()
        )
        self._app.add_handler(CommandHandler("morning", self._cmd_morning))

    def schedule_morning(self, at: time, tz: str) -> None:
        self.scheduler.add_job(
            self.send_morning,
            CronTrigger(hour=at.hour, minute=at.minute, timezone=tz),
            id="morning",
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
        )

    async def _start(self, _app: Application) -> None:
        self.scheduler.start()
        self._runner = web.AppRunner(self._web_app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self._http_host, self._http_port).start()
        _log.info("web: serving on http://%s:%s", self._http_host, self._http_port)

    async def _stop(self, _app: Application) -> None:
        self.scheduler.shutdown(wait=False)
        if self._runner is not None:
            await self._runner.cleanup()

    async def send_morning(self) -> None:
        await self._app.bot.send_message(
            chat_id=self._chat_id, text=MORNING_TEXT, reply_markup=self._markup
        )
        # Liveness ping (ADR-0017): only after the scheduled send went out.
        await self._heartbeat.ping()

    async def notify(self, text: str) -> None:
        await self._app.bot.send_message(chat_id=self._chat_id, text=text)

    async def _cmd_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        chat = update.effective_chat
        # Logged so ROUTINES_CHAT_ID can be checked against the real group id.
        _log.info("/morning from chat %s", chat.id if chat else None)
        if update.effective_message:
            await update.effective_message.reply_text(
                MORNING_TEXT, reply_markup=self._markup
            )

    def run_polling(self) -> None:
        self._app.run_polling()

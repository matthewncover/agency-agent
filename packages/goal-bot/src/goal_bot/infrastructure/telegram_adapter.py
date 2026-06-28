import logging
from datetime import date

from agency_profile.domain.entities import Person
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import Session

_log = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(
        self,
        token: str,
        chat_id: int,
        person_id: int,
        service: MorningService,
        scheduler=None,
    ) -> None:
        self._chat_id = chat_id
        self._person_id = person_id
        self._service = service
        self._sessions: dict[int, Session] = {}

        builder = Application.builder().token(token)
        if scheduler is not None:
            # APScheduler needs a running event loop; PTB owns the loop via
            # run_polling(), so we start the scheduler inside post_init.
            async def _start_scheduler(ptb_app: Application) -> None:
                scheduler.start()

            builder = builder.post_init(_start_scheduler)
        self._app = builder.build()
        self._app.add_handler(CommandHandler("morning", self._cmd_morning))
        self._app.add_handler(CommandHandler("whoami", self._cmd_whoami))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
        )

    def _auth(self, update: Update) -> bool:
        incoming = update.effective_chat.id if update.effective_chat else None
        ok = incoming == self._chat_id
        if not ok:
            _log.warning("auth rejected: incoming chat_id=%s, expected=%s", incoming, self._chat_id)
        return ok

    async def _cmd_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth(update):
            return
        session = self._service.fire_morning(self._person_id, date.today())
        self._sessions[self._chat_id] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth(update):
            return
        session = self._sessions.get(self._chat_id)
        if not session:
            return
        session = self._service.handle_reply(session, update.message.text)
        self._sessions[self._chat_id] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)

    async def _cmd_whoami(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._auth(update):
            return
        await update.message.reply_text(
            f"chat_id={update.effective_chat.id}, person_id={self._person_id}"
        )

    async def send(self, text: str) -> None:
        await self._app.bot.send_message(chat_id=self._chat_id, text=text)

    def run_morning_job(self, person: Person):
        """Return an async callable for the APScheduler job."""
        service = self._service
        person_id = self._person_id
        chat_id = self._chat_id
        sessions = self._sessions
        app = self._app

        async def _job() -> None:
            session = service.fire_morning(person_id, date.today())
            sessions[chat_id] = session
            if session.response_text:
                await app.bot.send_message(chat_id=chat_id, text=session.response_text)

        return _job

    def run_polling(self) -> None:
        self._app.run_polling()

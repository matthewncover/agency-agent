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

from goal_bot.application.heartbeat_port import HeartbeatPort, NoopHeartbeat
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import Session

_log = logging.getLogger(__name__)


class TelegramAdapter:
    """Multi-person Telegram front end (B7). Holds a chat→person mapping; each
    person gets their own morning job (fired at their local time) and inbound
    messages route by chat id to the right person's session. Auth is a
    membership check against the known chats."""

    def __init__(
        self,
        token: str,
        chat_person: dict[int, int],
        persons: dict[int, Person],
        service: MorningService,
        scheduler=None,
        heartbeat: HeartbeatPort | None = None,
    ) -> None:
        self._chat_person = dict(chat_person)  # chat_id -> person_id
        self._person_chat = {p: c for c, p in chat_person.items()}
        self._persons = dict(persons)  # person_id -> Person
        self._service = service
        self._heartbeat = heartbeat or NoopHeartbeat()
        self._sessions: dict[int, Session] = {}  # keyed by chat_id

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

    # --- routing (pure, unit-testable) ---

    def person_for_chat(self, chat_id: int | None) -> int | None:
        return self._chat_person.get(chat_id) if chat_id is not None else None

    def chat_for_person(self, person_id: int) -> int | None:
        return self._person_chat.get(person_id)

    def is_member(self, chat_id: int | None) -> bool:
        return chat_id in self._chat_person

    def _auth(self, update: Update) -> int | None:
        """Return the routed person_id if the chat is known, else None."""
        incoming = update.effective_chat.id if update.effective_chat else None
        person_id = self.person_for_chat(incoming)
        if person_id is None:
            _log.warning("auth rejected: unknown chat_id=%s", incoming)
        return person_id

    # --- handlers ---

    async def _cmd_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        person_id = self._auth(update)
        if person_id is None:
            return
        chat_id = update.effective_chat.id
        session = self._service.fire_morning(person_id, date.today())
        self._sessions[chat_id] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        person_id = self._auth(update)
        if person_id is None:
            return
        chat_id = update.effective_chat.id
        session = self._sessions.get(chat_id)
        if not session:
            return
        session = self._service.handle_reply(session, update.message.text)
        self._sessions[chat_id] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)

    async def _cmd_whoami(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        person_id = self._auth(update)
        if person_id is None:
            return
        await update.message.reply_text(
            f"chat_id={update.effective_chat.id}, person_id={person_id}"
        )

    async def send(self, chat_id: int, text: str) -> None:
        await self._app.bot.send_message(chat_id=chat_id, text=text)

    def morning_job_for(self, person_id: int):
        """An async APScheduler job that fires *this* person's morning and sends
        it to *their* chat."""
        service = self._service
        chat_id = self._person_chat[person_id]
        sessions = self._sessions
        app = self._app
        heartbeat = self._heartbeat

        async def _job() -> None:
            session = service.fire_morning(person_id, date.today())
            sessions[chat_id] = session
            if session.response_text:
                await app.bot.send_message(chat_id=chat_id, text=session.response_text)
                # Liveness ping (ADR-0017): only after the message actually went
                # out, and only on the *scheduled* path — a manual /morning must
                # not mask a dead scheduler. Keyed to delivery, never to whether
                # the user replies.
                await heartbeat.ping()

        return _job

    def run_polling(self) -> None:
        self._app.run_polling()

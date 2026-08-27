import logging
import re
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

from goal_bot import transcript
from goal_bot.application.heartbeat_port import HeartbeatPort, NoopHeartbeat
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import Session

_log = logging.getLogger(__name__)


def is_addressed(
    chat_type: str,
    text: str,
    bot_username: str,
    bot_id: int,
    reply_to_from_id: int | None,
) -> bool:
    """Explicit-addressing gate for group chats. Gating lives in code rather
    than in BotFather's privacy mode because that setting can't be trusted:
    an admin grant or a privacy toggle silently changes what Telegram
    delivers. Private chats are always addressed; in a group the message must
    be a reply to the bot's own message or @mention the bot."""
    if chat_type == "private":
        return True
    if reply_to_from_id is not None and reply_to_from_id == bot_id:
        return True
    return bool(re.search(rf"@{re.escape(bot_username)}\b", text, re.IGNORECASE))


def strip_mention(text: str, bot_username: str) -> str:
    """Remove @mentions of the bot so downstream sees the message itself."""
    return re.sub(
        rf"@{re.escape(bot_username)}\b", "", text, flags=re.IGNORECASE
    ).strip()


class TelegramAdapter:
    """Multi-person Telegram front end (B7/B8). The chat map defines which
    chats the bot lives in and where each person's morning job sends; identity
    comes from the speaker's user id when a user map is configured (shared
    chats, B8), else from the chat (legacy per-person chats). A message can
    only ever reach the speaker's own session — nobody can log outcomes or
    engage on another person's behalf. In group chats the bot only answers
    when explicitly addressed: /commands, replies to its own messages, or
    @mentions (see is_addressed)."""

    def __init__(
        self,
        token: str,
        chat_person: list[tuple[int, int]] | dict[int, int],
        persons: dict[int, Person],
        service: MorningService,
        scheduler=None,
        heartbeat: HeartbeatPort | None = None,
        user_person: dict[int, int] | None = None,
    ) -> None:
        pairs = (
            list(chat_person.items())
            if isinstance(chat_person, dict)
            else list(chat_person)
        )
        self._chat_persons: dict[int, list[int]] = {}  # chat_id -> [person_id]
        for chat_id, person_id in pairs:
            self._chat_persons.setdefault(chat_id, []).append(person_id)
        self._person_chat = {p: c for c, p in pairs}  # person_id -> send target
        self._user_person = dict(user_person or {})  # telegram user_id -> person_id
        self._persons = dict(persons)  # person_id -> Person
        self._service = service
        self._heartbeat = heartbeat or NoopHeartbeat()
        self._sessions: dict[tuple[int, int], Session] = {}  # (chat_id, person_id)

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

    def person_for(self, chat_id: int | None, user_id: int | None) -> int | None:
        """Resolve the acting person. Chat membership gates; with a user map
        the speaker decides identity, else the chat does (legacy). A known
        chat whose speaker is unmapped resolves to None — the message is
        ignored, never attributed to someone else."""
        if chat_id is None or chat_id not in self._chat_persons:
            return None
        if self._user_person:
            return self._user_person.get(user_id)
        persons = self._chat_persons[chat_id]
        return persons[0] if len(persons) == 1 else None

    def chat_for_person(self, person_id: int) -> int | None:
        return self._person_chat.get(person_id)

    def is_member(self, chat_id: int | None) -> bool:
        return chat_id in self._chat_persons

    def is_shared_chat(self, chat_id: int) -> bool:
        return len(self._chat_persons.get(chat_id, [])) > 1

    def _auth(self, update: Update) -> int | None:
        """Return the routed person_id, else None (and log why)."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        user_id = update.effective_user.id if update.effective_user else None
        person_id = self.person_for(chat_id, user_id)
        if person_id is None:
            if self.is_member(chat_id):
                # Onboarding aid: this is the line to read when wiring a new
                # person's telegram user id into TELEGRAM_USER_MAP.
                _log.warning(
                    "auth rejected: known chat_id=%s, unmapped user_id=%s",
                    chat_id,
                    user_id,
                )
            else:
                _log.warning("auth rejected: unknown chat_id=%s", chat_id)
        return person_id

    # --- handlers ---

    async def _cmd_morning(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        person_id = self._auth(update)
        if person_id is None:
            return
        chat_id = update.effective_chat.id
        transcript.log_message(chat_id, person_id, "in", "/morning")
        session = self._service.fire_morning(person_id, date.today())
        self._sessions[(chat_id, person_id)] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)
            transcript.log_message(chat_id, person_id, "out", session.response_text)

    async def _handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        person_id = self._auth(update)
        if person_id is None:
            return
        bot = context.bot
        reply_to = update.message.reply_to_message
        if not is_addressed(
            update.effective_chat.type,
            update.message.text or "",
            bot.username or "",
            bot.id,
            reply_to.from_user.id if reply_to and reply_to.from_user else None,
        ):
            return
        chat_id = update.effective_chat.id
        session = self._sessions.get((chat_id, person_id))
        if not session:
            return
        text = strip_mention(update.message.text, bot.username or "")
        transcript.log_message(chat_id, person_id, "in", text)
        session = self._service.handle_reply(session, text)
        self._sessions[(chat_id, person_id)] = session
        if session.response_text:
            await update.message.reply_text(session.response_text)
            transcript.log_message(chat_id, person_id, "out", session.response_text)

    async def _cmd_whoami(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Answers in any known chat, even for an unmapped speaker — that is
        # exactly the onboarding moment where someone needs their user id.
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not self.is_member(chat_id):
            return
        user_id = update.effective_user.id if update.effective_user else None
        person_id = self.person_for(chat_id, user_id)
        await update.message.reply_text(
            f"chat_id={chat_id}, user_id={user_id}, person_id={person_id}"
        )

    async def send(self, chat_id: int, text: str) -> None:
        await self._app.bot.send_message(chat_id=chat_id, text=text)

    def label_outbound(self, chat_id: int, person_id: int, text: str) -> str:
        """In a shared chat, unprompted sends carry the person's name so it is
        obvious whose morning this is; solo chats stay unadorned."""
        if not self.is_shared_chat(chat_id):
            return text
        person = self._persons.get(person_id)
        if person is None:
            return text
        return f"{person.display_name}:\n{text}"

    def morning_job_for(self, person_id: int):
        """An async APScheduler job that fires *this* person's morning and sends
        it to *their* chat."""
        service = self._service
        chat_id = self._person_chat[person_id]
        sessions = self._sessions
        app = self._app
        heartbeat = self._heartbeat
        label = self.label_outbound

        async def _job() -> None:
            session = service.fire_morning(person_id, date.today())
            sessions[(chat_id, person_id)] = session
            if session.response_text:
                text = label(chat_id, person_id, session.response_text)
                await app.bot.send_message(chat_id=chat_id, text=text)
                transcript.log_message(chat_id, person_id, "out", text)
                # Liveness ping (ADR-0017): only after the message actually went
                # out, and only on the *scheduled* path — a manual /morning must
                # not mask a dead scheduler. Keyed to delivery, never to whether
                # the user replies.
                await heartbeat.ping()

        return _job

    def run_polling(self) -> None:
        self._app.run_polling()

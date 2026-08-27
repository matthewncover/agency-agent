import logging
from dataclasses import dataclass

from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from agency_profile.infrastructure.engine import make_engine
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine
from task_tracker.application.query_client import TaskQueryClient
from task_tracker.infrastructure.task_query_client import PgTaskQueryClient

from goal_bot.application.heartbeat_port import HeartbeatPort, NoopHeartbeat
from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import MorningTurn
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.config import Settings, get_settings
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.infrastructure.anthropic_llm import AnthropicLLMAdapter
from goal_bot.infrastructure.heartbeat import HttpHeartbeat
from goal_bot.infrastructure.scheduler import schedule_morning
from goal_bot.infrastructure.telegram_adapter import TelegramAdapter
from goal_bot.server import RITUAL_TOOL_DEFS

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logging.getLogger("goal_bot").setLevel(logging.INFO)
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
_log = logging.getLogger(__name__)


@dataclass
class App:
    telegram: TelegramAdapter
    scheduler: AsyncIOScheduler
    tasks: TaskQueryClient


def build_task_query_client(engine: Engine) -> TaskQueryClient:
    """The published, read-only task-tracker client goal-bot uses for
    candidate-gathering + daily signal (ADR-0007). Not consumed by the morning
    flow yet — that's B2/B4; B1 just exposes it."""
    return PgTaskQueryClient(engine)


def build_heartbeat(settings: Settings) -> HeartbeatPort:
    """The liveness dead-man's-switch pinger (ADR-0017). Configured URL ⇒ HTTP
    adapter; unconfigured ⇒ no-op, so dev/tests need no external watchdog."""
    url = settings.heartbeat_url.strip()
    if url:
        return HttpHeartbeat(url, timeout=settings.heartbeat_timeout)
    return NoopHeartbeat()


def build_app(settings: Settings) -> App:
    _log.info("build_app: start (person_id=%s)", settings.person_id)
    engine = make_engine(settings.database_url)
    _log.info("build_app: engine created")
    goals = SqlAlchemyGoalRepository(engine)
    plans = SqlAlchemyPlanRepository(engine)
    wins = SqlAlchemyWinRepository(engine)
    profiles = SqlAlchemyProfileRepository(engine)
    tasks = build_task_query_client(engine)
    uc = GoalUseCases(
        goals=goals, plans=plans, wins=wins, profiles=profiles, tasks=tasks
    )
    _log.info("build_app: use-cases ready")

    llm = AnthropicLLMAdapter(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        effort=settings.anthropic_effort,
    )
    _log.info("build_app: LLM adapter ready")
    turn = MorningTurn(llm=llm, uc=uc, tool_defs=RITUAL_TOOL_DEFS)
    service = MorningService(
        goals=goals,
        plans=plans,
        wins=wins,
        turn=turn,
        tasks=tasks,
        profiles=profiles,
    )
    _log.info("build_app: service ready")

    # Resolve the chat→person mapping (B7). One entry = the A7 single-user case;
    # two = you + your partner, each keyed to their own chat + local morning.
    pairs = settings.chat_person_pairs()
    chat_person = {chat_id: person_id for chat_id, person_id in pairs}
    persons = {person_id: profiles.get_person(person_id) for _chat, person_id in pairs}
    _log.info("build_app: chat→person map = %s", chat_person)

    scheduler = AsyncIOScheduler()
    heartbeat = build_heartbeat(settings)
    _log.info("build_app: heartbeat = %s", type(heartbeat).__name__)
    _log.info("build_app: building TelegramAdapter")
    telegram = TelegramAdapter(
        token=settings.telegram_bot_token,
        chat_person=chat_person,
        persons=persons,
        service=service,
        scheduler=scheduler,
        heartbeat=heartbeat,
    )
    _log.info("build_app: TelegramAdapter ready")

    # One morning job per person, each at their own local time.
    for person_id, person in persons.items():
        schedule_morning(
            scheduler,
            run_morning=telegram.morning_job_for(person_id),
            person=person,
            debug_interval=settings.debug_morning_interval or None,
            job_id=f"morning-{person_id}",
        )
    _log.info("build_app: scheduled %d morning job(s)", len(persons))

    return App(telegram=telegram, scheduler=scheduler, tasks=tasks)


def run() -> None:
    _log.info("run: loading settings")
    settings = get_settings()
    _log.info("run: building app")
    app = build_app(settings)
    _log.info("run: starting run_polling")
    app.telegram.run_polling()  # starts event loop; scheduler starts via post_init

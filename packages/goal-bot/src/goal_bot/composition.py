import logging
from dataclasses import dataclass

from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from agency_profile.infrastructure.engine import make_engine
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from goal_bot.application.morning_service import MorningService
from goal_bot.application.morning_turn import MorningTurn
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.config import Settings, get_settings
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.infrastructure.anthropic_llm import AnthropicLLMAdapter
from goal_bot.infrastructure.scheduler import schedule_morning
from goal_bot.infrastructure.telegram_adapter import TelegramAdapter
from goal_bot.server import RITUAL_TOOL_DEFS

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("goal_bot").setLevel(logging.INFO)
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
_log = logging.getLogger(__name__)


@dataclass
class App:
    telegram: TelegramAdapter
    scheduler: AsyncIOScheduler


def build_app(settings: Settings) -> App:
    _log.info("build_app: start (person_id=%s)", settings.person_id)
    engine = make_engine(settings.database_url)
    _log.info("build_app: engine created")
    goals = SqlAlchemyGoalRepository(engine)
    plans = SqlAlchemyPlanRepository(engine)
    wins = SqlAlchemyWinRepository(engine)
    uc = GoalUseCases(goals=goals, plans=plans, wins=wins)
    _log.info("build_app: use-cases ready")

    llm = AnthropicLLMAdapter(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )
    _log.info("build_app: LLM adapter ready")
    turn = MorningTurn(llm=llm, uc=uc, tool_defs=RITUAL_TOOL_DEFS)
    service = MorningService(goals=goals, plans=plans, wins=wins, turn=turn)
    _log.info("build_app: service ready")

    scheduler = AsyncIOScheduler()
    _log.info("build_app: building TelegramAdapter")
    telegram = TelegramAdapter(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        person_id=settings.person_id,
        service=service,
        scheduler=scheduler,
    )
    _log.info("build_app: TelegramAdapter ready")

    _log.info("build_app: fetching person from DB")
    person = SqlAlchemyProfileRepository(engine).get_person(settings.person_id)
    _log.info("build_app: person=%s", person)

    schedule_morning(
        scheduler,
        run_morning=telegram.run_morning_job(person),
        person=person,
        debug_interval=settings.debug_morning_interval or None,
    )
    _log.info("build_app: schedule_morning done")

    return App(telegram=telegram, scheduler=scheduler)


def run() -> None:
    _log.info("run: loading settings")
    settings = get_settings()
    _log.info("run: building app")
    app = build_app(settings)
    _log.info("run: starting run_polling")
    app.telegram.run_polling()  # starts event loop; scheduler starts via post_init

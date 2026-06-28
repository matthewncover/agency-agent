from fastmcp import FastMCP
from sqlalchemy import Engine

from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.tools import authoring, reads, ritual

RITUAL_TOOLS = [
    "log_outcome", "lock_in_plan", "add_win", "record_reflection",
    "get_full_goal_list", "get_plan", "get_goal_detail", "get_active_chapter",
]
INGESTION_TOOLS = [
    "create_chapter", "create_goal", "create_goal_version", "update_goal",
    "get_goal_detail", "get_active_chapter",
]

# Anthropic-format tool schemas for the ritual grant (used by MorningTurn).
RITUAL_TOOL_DEFS: list[dict] = [
    {
        "name": "log_outcome",
        "description": (
            "Record an outcome the user actively reported (done|partial|not_done). "
            "Only call this when the person explicitly reports a result — "
            "never call it from silence or to record an unanswered touchpoint."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "daily_plan_item_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["done", "partial", "not_done"]},
                "quantity_actual": {"type": "number"},
            },
            "required": ["daily_plan_item_id", "status"],
        },
    },
    {
        "name": "lock_in_plan",
        "description": "Finalize the daily plan the user has explicitly agreed to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "daily_plan_id": {"type": "integer"},
                "explicit": {"type": "boolean"},
            },
            "required": ["daily_plan_id"],
        },
    },
    {
        "name": "add_win",
        "description": "Record a win the user manually reported, any time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "integer", "description": "person_id"},
                "text": {"type": "string"},
                "goal_id": {"type": "integer"},
            },
            "required": ["owner", "text"],
        },
    },
    {
        "name": "record_reflection",
        "description": "Record the 'what shifted' reflection for a plan item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "daily_plan_item_id": {"type": "integer"},
                "what_shifted": {"type": "string"},
            },
            "required": ["daily_plan_item_id", "what_shifted"],
        },
    },
    {
        "name": "get_full_goal_list",
        "description": "Fetch all active goals for the person on a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "integer", "description": "person_id"},
                "on": {"type": "string", "format": "date"},
            },
            "required": ["owner", "on"],
        },
    },
    {
        "name": "get_plan",
        "description": "Get (or create) the daily plan and its items for a date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "integer"},
                "on": {"type": "string", "format": "date"},
            },
            "required": ["owner", "on"],
        },
    },
    {
        "name": "get_goal_detail",
        "description": "Fetch a goal and all its versions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
            },
            "required": ["goal_id"],
        },
    },
    {
        "name": "get_active_chapter",
        "description": "Return the chapter active on a given date, or null.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "integer"},
                "on": {"type": "string", "format": "date"},
            },
            "required": ["owner", "on"],
        },
    },
]


def build_use_cases(engine: Engine) -> GoalUseCases:
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
    )


def build_server(engine: Engine) -> FastMCP:
    mcp = FastMCP("goal-bot")
    uc = build_use_cases(engine)
    ritual.register_ritual_tools(mcp, uc)
    reads.register_read_tools(mcp, uc)
    authoring.register_authoring_tools(mcp, uc)
    return mcp

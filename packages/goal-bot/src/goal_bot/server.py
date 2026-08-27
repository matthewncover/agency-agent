from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from fastmcp import FastMCP
from sqlalchemy import Engine
from task_tracker.infrastructure.task_query_client import PgTaskQueryClient

from goal_bot.application.ingestion import IngestionUseCases
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from goal_bot.tools import authoring, ingestion, reads, ritual

RITUAL_TOOLS = [
    "log_outcome",
    "revert_outcome",
    "lock_in_plan",
    "add_win",
    "record_reflection",
    "log_progress",
    # Reassessment lifecycle (§3.2) — create_goal_version is scoped to inline
    # re-anchoring; the other two are ritual-only lifecycle verbs.
    "set_goal_lifecycle",
    "set_rotation_pointer",
    "set_rotation_group_pointer",
    "create_goal_version",
    "get_full_goal_list",
    "get_plan",
    "get_goal_detail",
    "get_active_chapter",
    "get_miss_detail",
]
INGESTION_TOOLS = [
    "create_chapter",
    "create_goal",
    "create_goal_version",
    "create_goals",
    "create_goal_versions",
    "update_goal",
    # Rotation groups (ADR-0016) — authored structure, reconciled at re-ingest.
    "create_rotation_group",
    "archive_rotation_group",
    "list_rotation_groups",
    "get_full_goal_list",
    "get_goal_detail",
    "get_active_chapter",
    "get_goals_for_chapter",
    # Deterministic goal-setting / re-ingest surface (B2): the LLM is handed
    # prepared lists + classifications, it never guesses identity itself.
    "propose_candidates",
    "diff_chapter",
    "rollover",
    "check_goal_scope",
    # Session-safety read: which DB the server is bound to (ingestion step 0).
    "get_db_target",
]
# Reads in the ingestion grant: NO get_plan — ingestion never touches daily
# plans and get_plan has a get-or-create side-effect (mcp-tools §2/§3.4).
INGESTION_READS = [
    "get_full_goal_list",
    "get_goal_detail",
    "get_active_chapter",
    "get_goals_for_chapter",
]

# Anthropic-format tool schemas for the ritual grant (used by MorningTurn).
RITUAL_TOOL_DEFS: list[dict] = [
    {
        "name": "log_outcome",
        "description": (
            "Record an outcome the user actively reported (done|partial|not_done). "
            "For quantity/duration completion goals (e.g. a step count), pass the "
            "reported number as quantity_actual — this IS the way to log a number "
            "on a daily/quota/interval goal; log_progress is only for accumulation "
            "goals. Only call this when the person explicitly reports a result — "
            "never call it from silence or to record an unanswered touchpoint. "
            "A done one-off archives itself (complete, reversible via unarchive). "
            "Mis-logged something? Undo it with revert_outcome, then log correctly."
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
        "name": "revert_outcome",
        "description": (
            "Undo a mis-logged outcome on the user's explicit correction: "
            "restores the item to planned and clears quantity_actual; "
            "un-archives a one-off that auto-archived on done. Does NOT rewind "
            "rotation/interval pointers (use set_rotation_pointer / "
            "set_rotation_group_pointer), does NOT restore the carry-over "
            "counter, and never touches a partner's shared-completion item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "daily_plan_item_id": {"type": "integer"},
            },
            "required": ["daily_plan_item_id"],
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
        "name": "log_progress",
        "description": (
            "Accrue progress toward an accumulation goal's chapter target "
            "(e.g. +1h on the painting). The plan item's status derives from "
            "the logged progress — never call log_outcome for an accumulation "
            "goal. Exempt from miss semantics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "integer", "description": "person_id"},
                "goal_id": {"type": "integer"},
                "amount": {"type": "number"},
                "on": {"type": "string", "format": "date"},
                "unit": {"type": "string"},
            },
            "required": ["owner", "goal_id", "amount"],
        },
    },
    {
        "name": "set_goal_lifecycle",
        "description": (
            "Reassessment lifecycle action the USER explicitly chose: "
            "archive|unarchive (retire/redirect, or a one-off drop) · "
            "pause|activate (dormant, not dropped). NEVER call without an "
            "explicit choice in the conversation — the nudge only offers; the "
            "human decides. Never auto-drop."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "state": {
                    "type": "string",
                    "enum": ["archive", "unarchive", "pause", "activate"],
                },
            },
            "required": ["goal_id", "state"],
        },
    },
    {
        "name": "set_rotation_pointer",
        "description": (
            "Manually set a rotation goal's pointer ('today is a push-up day'). "
            "No completion attached; never a side effect of log_outcome."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "position": {"type": "integer"},
            },
            "required": ["goal_id", "position"],
        },
    },
    {
        "name": "set_rotation_group_pointer",
        "description": (
            "Manually set a rotation GROUP's pointer (cross-goal cadence, "
            "ADR-0016). No completion attached; never a side effect of "
            "log_outcome."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
                "position": {"type": "integer"},
            },
            "required": ["group_id", "position"],
        },
    },
    {
        "name": "create_goal_version",
        "description": (
            "Scoped to inline RE-ANCHORING only: lower a recurring goal's bar to "
            "the 95% floor as a new version (same goal_id, lower target). The "
            "server assigns version_no and closes the prior version. Use only in "
            "the reassessment flow on the user's explicit choice — not for "
            "general authoring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer"},
                "level": {"type": "string", "enum": ["need", "want"]},
                "definition": {"type": "string"},
                "recurrence_type": {"type": "string"},
                "recurrence_config": {"type": "object"},
                "completion_type": {"type": "string"},
                "why": {"type": "string"},
                "target_quantity": {"type": "number"},
                "quantity_unit": {"type": "string"},
                "obstacles": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "goal_id",
                "level",
                "definition",
                "recurrence_type",
                "recurrence_config",
                "completion_type",
            ],
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
    {
        "name": "get_miss_detail",
        "description": (
            "The engaged-miss count + day-by-day for ONE goal. Call this ONLY "
            "after the user has explicitly agreed to look at the pattern — never "
            "volunteer it, never headline the count, never name it relative to "
            "anyone else. Silence is never a miss; only self-reported not_done "
            "days appear here."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"goal_id": {"type": "integer"}},
            "required": ["goal_id"],
        },
    },
]


def build_use_cases(engine: Engine) -> GoalUseCases:
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
        profiles=SqlAlchemyProfileRepository(engine),  # shared-completion (B7)
        tasks=PgTaskQueryClient(engine),  # task_ref validation (ADR-0018)
    )


def build_ingestion_use_cases(engine: Engine) -> IngestionUseCases:
    return IngestionUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        profiles=SqlAlchemyProfileRepository(engine),
        tasks=PgTaskQueryClient(engine),
    )


def db_target_payload(engine: Engine) -> dict:
    """Sanitized description of the DB an MCP server is bound to (no password).
    `looks_like` follows the monorepo port convention: 5432 = local dev,
    5433 = prod via the ssh tunnel."""
    url = engine.url
    if url.database and url.database.endswith("_test"):
        looks_like = "test"
    elif url.port == 5433:
        looks_like = "prod (ssh tunnel :5433)"
    elif url.port in (None, 5432):
        looks_like = "dev (local :5432)"
    else:
        looks_like = "unknown"
    return {
        "host": url.host,
        "port": url.port,
        "database": url.database,
        "user": url.username,
        "looks_like": looks_like,
    }


def _register_db_target(mcp: FastMCP, engine: Engine) -> None:
    @mcp.tool
    def get_db_target() -> dict:
        """Which database this server is bound to — fixed at LAUNCH; `.env`
        edits do NOT apply until the server is reconnected. Call this FIRST in
        any ingestion session and show the user the answer before writing
        anything (ingestion step 0). Never returns the password."""
        return db_target_payload(engine)


def build_server(engine: Engine) -> FastMCP:
    mcp = FastMCP("goal-bot")
    uc = build_use_cases(engine)
    ritual.register_ritual_tools(mcp, uc)
    reads.register_read_tools(mcp, uc)
    authoring.register_authoring_tools(mcp, uc)
    ingestion.register_ingestion_tools(mcp, build_ingestion_use_cases(engine))
    _register_db_target(mcp, engine)
    return mcp


def build_ingestion_server(engine: Engine) -> FastMCP:
    """Ingestion grant: authoring + reads, minus get_plan. NO ritual write tools
    and NO daily-plan reads — ingestion never touches plans (mcp-tools §2/§3.4)."""
    mcp = FastMCP("goal-bot-ingestion")
    uc = build_use_cases(engine)
    authoring.register_authoring_tools(mcp, uc)
    reads.register_read_tools(mcp, uc, include=INGESTION_READS)
    ingestion.register_ingestion_tools(mcp, build_ingestion_use_cases(engine))
    _register_db_target(mcp, engine)
    return mcp

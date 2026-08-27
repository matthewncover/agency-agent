import json
from dataclasses import dataclass
from datetime import date

from goal_bot.application.llm_port import LLMPort, LLMResponse, ToolCall
from goal_bot.application.morning_context import MorningContext
from goal_bot.application.prompt import build_system_prompt
from goal_bot.application.use_cases import GoalUseCases

_RITUAL_GRANT: frozenset[str] = frozenset(
    {
        "log_outcome",
        "revert_outcome",
        "lock_in_plan",
        "add_win",
        "record_reflection",
        "log_progress",
        # Reassessment lifecycle (B6, §3.2) — fired ONLY on the user's explicit
        # choice; create_goal_version is scoped to inline re-anchoring. The nudge
        # only offers, so nothing here ever executes without a conversational choice.
        "set_goal_lifecycle",
        "set_rotation_pointer",
        "set_rotation_group_pointer",
        "create_goal_version",
        "get_full_goal_list",
        "get_plan",
        "get_goal_detail",
        "get_active_chapter",
        # Assent-gated (name-the-bar, OQ-COMP-1): the LLM may call this ONLY after
        # the user explicitly agrees to look at a chronic-miss pattern. The gate is
        # enforced by prompt + the count living nowhere else, not by dispatch.
        "get_miss_detail",
    }
)


@dataclass
class Session:
    ctx: MorningContext
    messages: list[dict]
    response_text: str


@dataclass
class MorningTurn:
    llm: LLMPort
    uc: GoalUseCases
    tool_defs: list[dict]
    max_steps: int = 4

    def start(self, ctx: MorningContext) -> Session:
        system = build_system_prompt(ctx)
        messages = [{"role": "user", "content": "Start the morning touchpoint."}]
        text, messages = self._run_loop(system, messages)
        return Session(ctx=ctx, messages=messages, response_text=text)

    def reply(self, session: Session, user_text: str) -> Session:
        system = build_system_prompt(session.ctx)
        messages = session.messages + [{"role": "user", "content": user_text}]
        text, messages = self._run_loop(system, messages)
        return Session(ctx=session.ctx, messages=messages, response_text=text)

    def _run_loop(self, system: str, messages: list[dict]) -> tuple[str, list[dict]]:
        last_text = ""
        for _ in range(self.max_steps):
            response: LLMResponse = self.llm.complete(system, messages, self.tool_defs)
            last_text = response.text

            content: list[dict] = []
            if response.text:
                content.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.args,
                    }
                )
            if not content:
                content = [{"type": "text", "text": ""}]

            messages = messages + [{"role": "assistant", "content": content}]

            if not response.tool_calls:
                break

            results = []
            for tc in response.tool_calls:
                result = self._dispatch(tc)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            messages = messages + [{"role": "user", "content": results}]

        return last_text, messages

    def _dispatch(self, tc: ToolCall) -> dict:
        if tc.name not in _RITUAL_GRANT:
            return {
                "error": (
                    f"tool '{tc.name}' is not in the ritual grant — no action taken"
                )
            }

        method = getattr(self.uc, tc.name, None)
        if method is None:
            return {"error": f"no dispatch implementation for '{tc.name}'"}

        args = dict(tc.args)
        if "on" in args and isinstance(args["on"], str):
            args["on"] = date.fromisoformat(args["on"])

        try:
            result = method(**args)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            return {"error": str(exc)}

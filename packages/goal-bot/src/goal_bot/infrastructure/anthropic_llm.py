import anthropic

from goal_bot import transcript
from goal_bot.application.llm_port import LLMPort, LLMResponse, ToolCall


class AnthropicLLMAdapter(LLMPort):
    def __init__(self, api_key: str, model: str, effort: str = "medium") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._effort = effort

    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        # Sonnet 5 runs adaptive thinking by default and thinking shares the
        # max_tokens budget — 1024 would risk a truncated reply after thinking.
        kwargs: dict = dict(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=messages,
            output_config={"effort": self._effort},
        )
        if tools:
            kwargs["tools"] = tools

        resp = self._client.messages.create(**kwargs)

        transcript.log_usage(
            model=self._model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_input_tokens=getattr(
                resp.usage, "cache_read_input_tokens", None
            ),
            cache_creation_input_tokens=getattr(
                resp.usage, "cache_creation_input_tokens", None
            ),
        )

        text = ""
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, args=dict(block.input))
                )

        return LLMResponse(text=text, tool_calls=tool_calls)

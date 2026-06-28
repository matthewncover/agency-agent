import anthropic

from goal_bot.application.llm_port import LLMPort, LLMResponse, ToolCall


class AnthropicLLMAdapter(LLMPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        resp = self._client.messages.create(**kwargs)

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

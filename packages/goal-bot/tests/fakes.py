from collections import deque

from goal_bot.application.llm_port import LLMPort, LLMResponse


class FakeLLM(LLMPort):
    """Scripted LLM that pops pre-configured responses from a queue."""

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._queue: deque[LLMResponse] = deque(responses or [])
        self.call_count = 0

    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        self.call_count += 1
        if self._queue:
            return self._queue.popleft()
        return LLMResponse(text="(no more scripted responses)")

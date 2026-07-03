from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ToolResult:
    id: str
    content: dict


class LLMPort(ABC):
    @abstractmethod
    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse: ...

    # messages: provider-agnostic [{role, content}]; tools: JSON-schema tool defs

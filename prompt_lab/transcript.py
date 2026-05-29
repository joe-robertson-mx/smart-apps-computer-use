"""Records what happened during one agent episode (for scoring + reporting)."""
from dataclasses import dataclass, field
from typing import Any, Optional

from prompt_lab.models import ModelSpec


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)


@dataclass
class ToolCall:
    action: str
    tool_input: dict
    output: Optional[str]
    error: Optional[str]
    has_image: bool


@dataclass
class Transcript:
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = ""
    steps: int = 0           # number of model invocations
    user_prompts: int = 0    # conversational: how many user prompts were issued
    wall_seconds: float = 0.0

    def cost(self, spec: ModelSpec) -> float:
        return (self.usage.input_tokens / 1_000_000 * spec.price_in
                + self.usage.output_tokens / 1_000_000 * spec.price_out)

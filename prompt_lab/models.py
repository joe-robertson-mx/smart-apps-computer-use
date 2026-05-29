"""Per-model Bedrock specs: model id, computer-use tool version + beta flag, display, price.

Ground truth for the ids/versions/betas is the repo files
`claude-opus-4-7-model-details.txt` and `claude-sonnet-4-5-model-details.txt`.
Prices are list $/million tokens — verify against current Bedrock eu-west-1 pricing.
"""
import os
from dataclasses import dataclass

# Display dimensions the executor's screen is at. MUST match the real desktop
# resolution on the host (the executor does not scale coordinates). Overridable
# via env so the lab can be aligned to the actual host without code changes.
_W = int(os.getenv("PROMPT_LAB_W", "1280"))
_H = int(os.getenv("PROMPT_LAB_H", "800"))


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    tool_type: str          # Anthropic computer-use tool "type" string
    beta_flag: str          # anthropic_beta value
    display_width: int
    display_height: int
    display_number: int
    price_in: float         # $/million input tokens
    price_out: float        # $/million output tokens


MODELS = {
    "sonnet-4-5": ModelSpec(
        key="sonnet-4-5",
        model_id="eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        tool_type="computer_20250124",
        beta_flag="computer-use-2025-01-24",
        display_width=_W,
        display_height=_H,
        display_number=1,
        price_in=3.0,
        price_out=15.0,
    ),
    "opus-4-7": ModelSpec(
        key="opus-4-7",
        model_id="eu.anthropic.claude-opus-4-7",
        tool_type="computer_20251124",
        beta_flag="computer-use-2025-11-24",
        display_width=_W,
        display_height=_H,
        display_number=1,
        price_in=15.0,
        price_out=75.0,
    ),
}


def spec_for(key: str) -> ModelSpec:
    try:
        return MODELS[key]
    except KeyError:
        raise ValueError(f"Unknown model key: {key!r}. Known: {sorted(MODELS)}")

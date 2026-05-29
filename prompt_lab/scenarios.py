"""Load a scenario YAML: target app + case data + expected record + (script | goal)."""
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class Scenario:
    id: str
    mode: str               # "single_prompt" | "conversational"
    target: str             # "warranty" | "returns"
    case: dict
    expected_record: dict
    script: list[str] = field(default_factory=list)
    goal: Optional[str] = None
    max_user_prompts: int = 0


def load_scenario(path: str) -> Scenario:
    data = yaml.safe_load(open(path, encoding="utf-8"))
    return Scenario(
        id=data["id"],
        mode=data["mode"],
        target=data["target"],
        case=data.get("case", {}),
        expected_record=data.get("expected_record", {}),
        script=data.get("script", []) or [],
        goal=data.get("goal"),
        max_user_prompts=int(data.get("max_user_prompts", 0)),
    )

"""Deterministic driver — replays a fixed list of user prompts (the demo script)."""
from typing import Optional

from prompt_lab.transcript import Transcript


class ScriptedDriver:
    def __init__(self, prompts: list[str]):
        self._prompts = list(prompts)
        self._i = 0

    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        if self._i >= len(self._prompts):
            return None
        prompt = self._prompts[self._i]
        self._i += 1
        return prompt

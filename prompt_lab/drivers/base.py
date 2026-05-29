"""A Driver supplies the next user prompt in a conversational episode, or None when done."""
from typing import Optional, Protocol

from prompt_lab.transcript import Transcript


class Driver(Protocol):
    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        ...

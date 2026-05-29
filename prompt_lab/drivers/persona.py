"""LLM persona driver — plays the presenter, emitting the next instruction toward a goal.

`complete(system, user) -> str` is injected (defaults wrap BedrockClient.complete_text),
so this is unit-testable with a stub. The persona returns the literal "TASK_COMPLETE"
when it judges the goal met; that maps to None (episode ends).
"""
from typing import Callable, Optional

from prompt_lab.transcript import Transcript

DONE = "TASK_COMPLETE"

_SYSTEM_TEMPLATE = (
    "You are a demo presenter directing a computer-use agent toward this goal:\n"
    "{goal}\n\n"
    "Each turn, look at the agent's latest message and issue the single next short "
    "instruction to move toward the goal. When the goal is fully met, reply with "
    "exactly {done}."
)


class PersonaDriver:
    def __init__(self, goal: str, complete: Callable[[str, str], str], max_turns: int = 6):
        self.goal = goal
        self._complete = complete
        self._max_turns = max_turns
        self._turns = 0

    def _last_agent_text(self, transcript: Transcript) -> str:
        for msg in reversed(transcript.messages):
            if msg.get("role") == "assistant":
                return "".join(b.get("text", "") for b in msg.get("content", [])
                               if b.get("type") == "text")
        return "(no message yet)"

    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        if self._turns >= self._max_turns:
            return None
        self._turns += 1
        system = _SYSTEM_TEMPLATE.format(goal=self.goal, done=DONE)
        user = f"Agent's latest message:\n{self._last_agent_text(transcript)}"
        reply = self._complete(system, user).strip()
        if reply == DONE or not reply:
            return None
        return reply

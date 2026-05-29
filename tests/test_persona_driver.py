from prompt_lab.drivers.persona import PersonaDriver
from prompt_lab.transcript import Transcript


def test_persona_returns_next_prompt_from_complete_fn():
    calls = []

    def fake_complete(system, user):
        calls.append((system, user))
        return "Please set the courier to DHL."

    d = PersonaDriver(goal="create a dispatch record", complete=fake_complete)
    t = Transcript()
    t.messages.append({"role": "assistant", "content": [{"type": "text", "text": "Which courier?"}]})
    out = d.next_prompt(t)
    assert out == "Please set the courier to DHL."
    assert "create a dispatch record" in calls[0][0]  # goal in system prompt


def test_persona_done_sentinel_returns_none():
    d = PersonaDriver(goal="g", complete=lambda s, u: "TASK_COMPLETE")
    assert d.next_prompt(Transcript()) is None


def test_persona_respects_max_turns():
    d = PersonaDriver(goal="g", complete=lambda s, u: "keep going", max_turns=2)
    t = Transcript()
    assert d.next_prompt(t) == "keep going"
    assert d.next_prompt(t) == "keep going"
    assert d.next_prompt(t) is None

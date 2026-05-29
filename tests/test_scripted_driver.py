from prompt_lab.drivers.scripted import ScriptedDriver
from prompt_lab.transcript import Transcript


def test_scripted_driver_yields_prompts_then_none():
    d = ScriptedDriver(["first", "second"])
    t = Transcript()
    assert d.next_prompt(t) == "first"
    assert d.next_prompt(t) == "second"
    assert d.next_prompt(t) is None

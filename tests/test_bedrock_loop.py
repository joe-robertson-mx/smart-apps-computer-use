from prompt_lab.bedrock_loop import run_episode
from prompt_lab.models import spec_for


class FakeBedrock:
    """Returns queued assistant messages in order."""
    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, spec, system, messages, max_tokens=1024):
        return self._responses.pop(0)


class FakeExecutor:
    def __init__(self):
        self.actions = []

    def act(self, tool_input):
        from prompt_lab.executor_client import ExecResult
        self.actions.append(tool_input)
        return ExecResult(output="ok", image_b64="IMG", error=None)


def _tool_use(action):
    return {"role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "computer",
                         "input": {"action": action}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 2}}


def _end_turn(text="done"):
    return {"role": "assistant",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1}}


def test_single_prompt_episode_runs_actions_until_end_turn():
    bedrock = FakeBedrock([_tool_use("screenshot"), _tool_use("left_click"), _end_turn()])
    executor = FakeExecutor()
    t = run_episode(bedrock, executor, spec_for("sonnet-4-5"),
                    system="SYS", user_prompt="fill the form", step_cap=10)

    assert t.stop_reason == "end_turn"
    assert [c.action for c in t.tool_calls] == ["screenshot", "left_click"]
    assert executor.actions == [{"action": "screenshot"}, {"action": "left_click"}]
    assert t.usage.output_tokens == 5  # 2 + 2 + 1


def test_step_cap_stops_runaway():
    bedrock = FakeBedrock([_tool_use("screenshot")] * 100)
    t = run_episode(bedrock, FakeExecutor(), spec_for("sonnet-4-5"),
                    system="s", user_prompt="go", step_cap=3)
    assert t.stop_reason == "step_cap"
    assert t.steps == 3


def test_conversational_driver_injects_next_prompt():
    # turn 1: end_turn -> driver gives "next" -> turn 2: end_turn -> driver done
    bedrock = FakeBedrock([_end_turn("turn1"), _end_turn("turn2")])

    class TwoStepDriver:
        def __init__(self):
            self.calls = 0
        def next_prompt(self, transcript):
            self.calls += 1
            return "do the next thing" if self.calls == 1 else None

    driver = TwoStepDriver()
    t = run_episode(bedrock, FakeExecutor(), spec_for("sonnet-4-5"),
                    system="s", user_prompt="start", step_cap=10,
                    driver=driver, max_user_prompts=4)
    assert t.user_prompts == 1
    assert t.stop_reason == "end_turn"

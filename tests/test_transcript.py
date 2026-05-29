from prompt_lab.transcript import Usage, ToolCall, Transcript
from prompt_lab.models import spec_for


def test_usage_add_accumulates():
    u = Usage()
    u.add(10, 5)
    u.add(2, 3)
    assert u.input_tokens == 12 and u.output_tokens == 8


def test_transcript_cost_uses_model_price():
    t = Transcript()
    t.usage.add(1_000_000, 1_000_000)
    spec = spec_for("sonnet-4-5")  # 3 in / 15 out per million
    assert t.cost(spec) == 18.0


def test_transcript_records_tool_calls_and_steps():
    t = Transcript()
    t.tool_calls.append(ToolCall(action="left_click", tool_input={"coordinate": [1, 2]},
                                 output="ok", error=None, has_image=True))
    t.steps = 3
    t.stop_reason = "end_turn"
    assert len(t.tool_calls) == 1
    assert t.tool_calls[0].action == "left_click"
    assert t.steps == 3

from prompt_lab.runner import run_matrix
from prompt_lab.prompts import PromptVariant
from prompt_lab.scenarios import Scenario
from prompt_lab.executor_client import ExecResult


class FakeBedrock:
    def invoke(self, spec, system, messages, max_tokens=1024):
        return {"role": "assistant",
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 3, "output_tokens": 1}}


class FakeExecutor:
    def act(self, tool_input):
        return ExecResult(output="ok", image_b64="IMG")


class FakeControl:
    def __init__(self, records):
        self._records = records
    def setup(self, app, case):
        return {"ready": True, "baseline_count": 0}
    def records(self, app):
        return {"records": self._records, "count": len(self._records)}


def test_run_matrix_scores_each_cell():
    variant = PromptVariant(id="warranty_v1", system="SYS",
                            user_template="do {recommended_action} ref DISP-{uuid}")
    scenario = Scenario(id="warranty-wheel-replacement", mode="single_prompt", target="warranty",
                        case={"recommended_action": "replace", "uuid": "A1B2C3"},
                        expected_record={"Status": "Replacement Approved"})
    good_record = {"Status": "Replacement Approved"}

    cells = run_matrix(
        variants=[variant], scenarios=[scenario], model_keys=["sonnet-4-5"], repeats=1,
        bedrock=FakeBedrock(), executor=FakeExecutor(), control=FakeControl([good_record]),
        persona_complete=lambda s, u: "TASK_COMPLETE",
    )
    assert len(cells) == 1
    assert cells[0]["passed"] is True
    assert cells[0]["variant"] == "warranty_v1"
    assert cells[0]["model"] == "sonnet-4-5"

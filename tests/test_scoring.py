from prompt_lab.scoring import score, ScoreResult
from prompt_lab.scenarios import Scenario
from prompt_lab.transcript import Transcript, ToolCall


def _scenario():
    return Scenario(
        id="s", mode="single_prompt", target="warranty",
        case={"uuid": "A1B2C3"},
        expected_record={"Status": "Replacement Approved",
                         "DispatchRef": "DISP-A1B2C3",
                         "Resolution": {"contains": "replacement"}},
    )


def _ok_transcript():
    t = Transcript()
    t.stop_reason = "end_turn"
    t.steps = 5
    return t


def test_pass_when_record_matches_and_safe():
    rec = {"Status": "Replacement Approved", "DispatchRef": "DISP-A1B2C3",
           "Resolution": "Approved replacement of wheel"}
    res = score(_scenario(), [rec], _ok_transcript(), step_cap=30, max_user_prompts=0)
    assert isinstance(res, ScoreResult)
    assert res.passed is True
    assert res.reasons == []


def test_fail_when_status_pending():
    rec = {"Status": "Pending", "DispatchRef": "DISP-A1B2C3", "Resolution": "replacement"}
    res = score(_scenario(), [rec], _ok_transcript(), step_cap=30, max_user_prompts=0)
    assert res.passed is False
    assert any("Status" in r for r in res.reasons)


def test_fail_when_no_record():
    res = score(_scenario(), [], _ok_transcript(), step_cap=30, max_user_prompts=0)
    assert res.passed is False
    assert any("no record" in r.lower() for r in res.reasons)


def test_fail_when_multiple_records_submitted():
    rec = {"Status": "Replacement Approved", "DispatchRef": "DISP-A1B2C3", "Resolution": "replacement"}
    res = score(_scenario(), [rec, rec], _ok_transcript(), step_cap=30, max_user_prompts=0)
    assert res.passed is False
    assert any("exactly one" in r.lower() for r in res.reasons)


def test_fail_when_step_cap_hit():
    t = _ok_transcript()
    t.stop_reason = "step_cap"
    rec = {"Status": "Replacement Approved", "DispatchRef": "DISP-A1B2C3", "Resolution": "replacement"}
    res = score(_scenario(), [rec], t, step_cap=30, max_user_prompts=0)
    assert res.passed is False
    assert any("step cap" in r.lower() for r in res.reasons)


def test_fail_on_destructive_action():
    t = _ok_transcript()
    t.tool_calls.append(ToolCall(action="left_click", tool_input={}, output="Clear pressed",
                                 error=None, has_image=True))
    rec = {"Status": "Replacement Approved", "DispatchRef": "DISP-A1B2C3", "Resolution": "replacement"}
    res = score(_scenario(), [rec], t, step_cap=30, max_user_prompts=0,
                destructive_markers=["Clear pressed"])
    assert res.passed is False
    assert any("destructive" in r.lower() for r in res.reasons)

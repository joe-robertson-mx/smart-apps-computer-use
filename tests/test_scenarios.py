from prompt_lab.scenarios import load_scenario, Scenario


def test_load_single_prompt_scenario(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text(
        "id: warranty-wheel-replacement\n"
        "mode: single_prompt\n"
        "target: warranty\n"
        "case:\n"
        "  case_id: EQ-2026-0042\n"
        "  recommended_action: Approve replacement\n"
        "  uuid: A1B2C3\n"
        "expected_record:\n"
        "  Status: Replacement Approved\n"
        "  Resolution: {contains: replacement}\n",
        encoding="utf-8",
    )
    s = load_scenario(str(f))
    assert isinstance(s, Scenario)
    assert s.mode == "single_prompt"
    assert s.target == "warranty"
    assert s.case["uuid"] == "A1B2C3"
    assert s.expected_record["Status"] == "Replacement Approved"
    assert s.script == [] and s.goal is None and s.max_user_prompts == 0


def test_load_conversational_scenario(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(
        "id: returns\n"
        "mode: conversational\n"
        "target: returns\n"
        "case: {case_id: EQ-2026-0042}\n"
        "expected_record: {dispatch_type: Wheel Replacement}\n"
        "script: ['open portal', 'submit']\n"
        "goal: create a dispatch record\n"
        "max_user_prompts: 4\n",
        encoding="utf-8",
    )
    s = load_scenario(str(f))
    assert s.mode == "conversational"
    assert s.script == ["open portal", "submit"]
    assert s.goal == "create a dispatch record"
    assert s.max_user_prompts == 4

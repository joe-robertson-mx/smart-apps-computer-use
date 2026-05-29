from prompt_lab.prompts import load_variant, render_user, PromptVariant


def test_load_variant_splits_system_and_user(tmp_path):
    f = tmp_path / "warranty_v1.md"
    f.write_text(
        "## system\n"
        "You are an automation agent.\n\n"
        "## user\n"
        "Resolution: {recommended_action}; Dispatch Ref: DISP-{uuid}.\n",
        encoding="utf-8",
    )
    v = load_variant(str(f))
    assert isinstance(v, PromptVariant)
    assert v.id == "warranty_v1"
    assert v.system == "You are an automation agent."
    assert "Dispatch Ref: DISP-{uuid}" in v.user_template


def test_render_user_fills_placeholders():
    v = PromptVariant(id="x", system="s", user_template="Do {recommended_action} ref DISP-{uuid}")
    out = render_user(v, {"recommended_action": "replace wheel", "uuid": "A1B2C3"})
    assert out == "Do replace wheel ref DISP-A1B2C3"

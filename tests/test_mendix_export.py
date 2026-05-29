from prompt_lab.mendix_export import export_variant
from prompt_lab.prompts import PromptVariant


def test_export_renders_paste_ready_blocks():
    v = PromptVariant(id="warranty_v1", system="You are an agent.",
                      user_template="Resolution: {recommended_action}; ref DISP-{uuid}.")
    text = export_variant(v, {"recommended_action": "replace wheel", "uuid": "A1B2C3"})
    assert "TestSystemPrompt" in text
    assert "You are an agent." in text
    assert "TestUserPrompt" in text
    assert "Resolution: replace wheel; ref DISP-A1B2C3." in text

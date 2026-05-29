import pytest
from prompt_lab.models import MODELS, spec_for, ModelSpec


def test_known_models_present():
    assert set(MODELS) == {"sonnet-4-5", "opus-4-7"}


def test_spec_for_returns_spec_with_tool_version_and_beta():
    spec = spec_for("sonnet-4-5")
    assert isinstance(spec, ModelSpec)
    assert spec.model_id == "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert spec.tool_type == "computer_20250124"
    assert spec.beta_flag == "computer-use-2025-01-24"
    assert spec.display_width == 1280 and spec.display_height == 800


def test_opus_uses_newer_tool_version():
    spec = spec_for("opus-4-7")
    assert spec.model_id == "eu.anthropic.claude-opus-4-7"
    assert spec.tool_type == "computer_20251124"
    assert spec.beta_flag == "computer-use-2025-11-24"


def test_spec_for_unknown_raises():
    with pytest.raises(ValueError):
        spec_for("gpt-9")

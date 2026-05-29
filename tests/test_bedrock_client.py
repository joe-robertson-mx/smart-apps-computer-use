from prompt_lab.bedrock_client import build_body, parse_response
from prompt_lab.models import spec_for


def test_build_body_includes_beta_tool_and_prompts():
    spec = spec_for("sonnet-4-5")
    messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    body = build_body(spec, system="SYS", messages=messages, max_tokens=1024)

    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["anthropic_beta"] == ["computer-use-2025-01-24"]
    assert body["system"] == "SYS"
    assert body["messages"] == messages
    assert body["max_tokens"] == 1024
    tool = body["tools"][0]
    assert tool["type"] == "computer_20250124"
    assert tool["name"] == "computer"
    assert tool["display_width_px"] == 1280
    assert tool["display_height_px"] == 800
    assert tool["display_number"] == 1


def test_parse_response_returns_message_dict():
    raw = {"role": "assistant",
           "content": [{"type": "text", "text": "done"}],
           "stop_reason": "end_turn",
           "usage": {"input_tokens": 7, "output_tokens": 3}}
    msg = parse_response(raw)
    assert msg["stop_reason"] == "end_turn"
    assert msg["usage"]["input_tokens"] == 7

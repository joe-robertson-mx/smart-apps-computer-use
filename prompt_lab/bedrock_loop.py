"""The agent loop — what the Mendix microflow does, in Python.

Invokes Bedrock, executes each `computer` tool-use via the REST executor, feeds the
screenshot back as a tool_result, and repeats until end_turn / step cap. In
conversational mode a driver supplies the next user prompt when the model yields.
"""
import time
from typing import Optional

from prompt_lab.models import ModelSpec
from prompt_lab.transcript import ToolCall, Transcript


def _tool_uses(message: dict) -> list[dict]:
    return [b for b in message.get("content", []) if b.get("type") == "tool_use"]


def run_episode(bedrock, executor, spec: ModelSpec, system: str, user_prompt: str,
                step_cap: int = 30, driver=None, max_user_prompts: int = 0) -> Transcript:
    t = Transcript()
    started = time.monotonic()
    t.messages.append({"role": "user", "content": [{"type": "text", "text": user_prompt}]})

    while True:
        message = bedrock.invoke(spec, system, t.messages, max_tokens=1024)
        t.steps += 1
        t.messages.append({"role": message.get("role", "assistant"),
                           "content": message.get("content", [])})
        usage = message.get("usage", {})
        t.usage.add(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

        uses = _tool_uses(message)
        if uses:
            results = []
            for use in uses:
                res = executor.act(use.get("input", {}))
                content = []
                if res.image_b64:
                    content.append({"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": res.image_b64}})
                content.append({"type": "text", "text": res.error or res.output or ""})
                results.append({"type": "tool_result", "tool_use_id": use.get("id"),
                                "content": content, "is_error": res.error is not None})
                t.tool_calls.append(ToolCall(
                    action=use.get("input", {}).get("action", "?"),
                    tool_input=use.get("input", {}),
                    output=res.output, error=res.error, has_image=res.image_b64 is not None))
            t.messages.append({"role": "user", "content": results})
        else:
            # Model yielded. In conversational mode, ask the driver for the next prompt.
            t.stop_reason = message.get("stop_reason", "end_turn")
            if driver is not None and t.user_prompts < max_user_prompts:
                nxt = driver.next_prompt(t)
                if nxt:
                    t.user_prompts += 1
                    t.messages.append({"role": "user",
                                       "content": [{"type": "text", "text": nxt}]})
                    continue
            break

        if t.steps >= step_cap:
            t.stop_reason = "step_cap"
            break

    t.wall_seconds = time.monotonic() - started
    return t

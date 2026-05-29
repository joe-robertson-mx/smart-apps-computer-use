"""Thin Bedrock adapter using invoke_model with the native Anthropic Messages API.

invoke_model with the Messages payload is the stable, well-documented path for
computer use on Bedrock and matches the Anthropic reference loop. build_body and
parse_response are pure (unit-tested); BedrockClient.invoke is the boto3 wrapper
(exercised live, not in unit tests).
"""
import json
from typing import Any

from prompt_lab.models import ModelSpec


def build_body(spec: ModelSpec, system: str, messages: list[dict], max_tokens: int = 1024) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "anthropic_beta": [spec.beta_flag],
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "tools": [{
            "type": spec.tool_type,
            "name": "computer",
            "display_width_px": spec.display_width,
            "display_height_px": spec.display_height,
            "display_number": spec.display_number,
        }],
    }


def parse_response(raw: dict) -> dict:
    """Return the assistant message dict (content/stop_reason/usage)."""
    return raw


class BedrockClient:
    def __init__(self, region: str = "eu-west-1", profile: str | None = None):
        import boto3  # imported lazily so unit tests don't need boto3 configured
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self._client = session.client("bedrock-runtime", region_name=region)

    def invoke(self, spec: ModelSpec, system: str, messages: list[dict], max_tokens: int = 1024) -> dict:
        body = build_body(spec, system, messages, max_tokens)
        resp = self._client.invoke_model(modelId=spec.model_id, body=json.dumps(body))
        return parse_response(json.loads(resp["body"].read()))

    def complete_text(self, spec: ModelSpec, system: str, user: str, max_tokens: int = 512) -> str:
        """Plain text completion (no tools) — used by the persona driver."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        }
        resp = self._client.invoke_model(modelId=spec.model_id, body=json.dumps(body))
        msg = json.loads(resp["body"].read())
        parts = [b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text"]
        return "".join(parts).strip()

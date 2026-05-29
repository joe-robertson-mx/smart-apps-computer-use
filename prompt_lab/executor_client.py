"""Client for the existing windows_server.py POST /computer_tool contract.

Maps a Claude `computer` tool-use input dict onto the JSON the executor expects,
and parses the {output, base64image} | {error_message} response.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ExecResult:
    output: Optional[str] = None
    image_b64: Optional[str] = None
    error: Optional[str] = None


def _http_transport(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The executor returns 400 + {"error_message": ...} for a failed action.
        # Read that body so the loop can feed the error back to the model.
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"error_message": f"HTTP {exc.code}: {exc.reason}"}


class ExecutorClient:
    def __init__(self, base_url: str, transport: Callable[[str, dict], dict] = _http_transport):
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def act(self, tool_input: dict) -> ExecResult:
        # Drop None values so the executor sees only the keys for this action.
        payload = {k: v for k, v in tool_input.items() if v is not None}
        # Mimic the Mendix mapping: Claude's `key` action carries the key combo in
        # `text`, but the executor reads it from `key`.
        if payload.get("action") == "key" and "key" not in payload and "text" in payload:
            payload["key"] = payload.pop("text")
        body = self._transport(f"{self.base_url}/computer_tool", payload)
        if body.get("error_message"):
            return ExecResult(error=body["error_message"])
        return ExecResult(output=body.get("output"), image_b64=body.get("base64image"))

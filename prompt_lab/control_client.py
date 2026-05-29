"""Client for the host control endpoints (scenario setup/reset + records read)."""
import json
import urllib.parse
import urllib.request
from typing import Callable


def _http_transport(method: str, url: str, payload: dict | None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


class ControlClient:
    def __init__(self, base_url: str, transport: Callable[[str, str, dict | None], dict] = _http_transport):
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def setup(self, app: str, case: dict) -> dict:
        return self._transport("POST", f"{self.base_url}/control/setup",
                               {"app": app, "case": case})

    def records(self, app: str) -> dict:
        q = urllib.parse.urlencode({"app": app})
        return self._transport("GET", f"{self.base_url}/control/records?{q}", None)

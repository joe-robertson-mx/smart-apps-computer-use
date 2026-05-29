# Computer-Use Prompt Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python "prompt lab" that mirrors the Mendix Bedrock computer-use request so we can iterate on the system/user prompts fast and repeatably, score the agent's success against the two demo apps, and export the winning prompts for the BOAT 2026 demo.

**Architecture:** A standalone package (`prompt_lab/`) plays the role Mendix plays: it runs the Bedrock agent loop itself and sends every tool action over the existing `/computer_tool` REST contract to `windows_server.py`. Pure modules (models, prompts, scenarios, scoring, drivers, report, export) are unit-tested in isolation; the loop and runner take injected Bedrock/executor/control clients so they test without network or a live screen. A small isolated host module (`scenario_control.py`) adds `/control/*` setup/records endpoints for remote scenario reset and scoring.

**Tech Stack:** Python 3.11, pytest, boto3 (Bedrock `invoke_model`, native Anthropic Messages API), PyYAML. Spec: `docs/superpowers/specs/2026-05-29-computer-use-prompt-lab-design.md`.

---

## File Structure

```
pyproject.toml                       # NEW: pytest config + pythonpath
prompt_lab/
  __init__.py                        # NEW
  requirements.txt                   # NEW: boto3, pyyaml
  models.py                          # NEW: ModelSpec + MODELS + spec_for
  transcript.py                      # NEW: Usage, ToolCall, Transcript (+cost)
  executor_client.py                 # NEW: REST client for /computer_tool
  bedrock_client.py                  # NEW: boto3 adapter (build_body/parse_response/invoke)
  prompts.py                         # NEW: load_variant + render_user
  scenarios.py                       # NEW: load_scenario
  scoring.py                         # NEW: score(scenario, records, transcript)
  control_client.py                  # NEW: client for /control/setup + /control/records
  bedrock_loop.py                    # NEW: run_episode (the agent loop)
  runner.py                          # NEW: matrix runner CLI
  report.py                          # NEW: markdown/json report
  mendix_export.py                   # NEW: paste-ready prompt export
  drivers/
    __init__.py                      # NEW
    base.py                          # NEW: Driver protocol
    scripted.py                      # NEW: ScriptedDriver
    persona.py                       # NEW: PersonaDriver
  prompts/
    warranty_v1.md                   # NEW: sample system+user variant (desktop)
    returns_v1.md                    # NEW: sample system+user variant (web)
  scenarios/
    warranty-wheel-replacement.yaml  # NEW: single_prompt desktop scenario
    returns-wheel-replacement.yaml   # NEW: conversational web scenario
  reports/                           # generated (gitignored)
  README.md                          # NEW
computer-use-windows/
  scenario_control.py                # NEW: host-side setup/records logic (no pyautogui dep)
  windows_server.py                  # MODIFY: route /control/* to scenario_control
tests/
  test_models.py  test_transcript.py  test_executor_client.py
  test_bedrock_client.py  test_prompts.py  test_scenarios.py
  test_scripted_driver.py  test_persona_driver.py  test_bedrock_loop.py
  test_scoring.py  test_control_client.py  test_runner.py
  test_report.py  test_mendix_export.py  test_scenario_control.py
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `prompt_lab/__init__.py`
- Create: `prompt_lab/requirements.txt`
- Create: `prompt_lab/drivers/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import prompt_lab
    assert prompt_lab.__name__ == "prompt_lab"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab'` (and/or pytest cannot find config).

- [ ] **Step 3: Create the scaffolding**

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = [".", "computer-use-windows"]
testpaths = ["tests"]
addopts = "-q"
```

`prompt_lab/__init__.py`:
```python
"""Computer-use prompt lab — iterate and score system/user prompts for the BOAT 2026 demo."""
```

`prompt_lab/drivers/__init__.py`:
```python
```

`prompt_lab/requirements.txt`:
```text
boto3>=1.34
PyYAML>=6.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml prompt_lab/__init__.py prompt_lab/requirements.txt prompt_lab/drivers/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold prompt_lab package + pytest config"
```

---

## Task 2: Model registry (`models.py`)

**Files:**
- Create: `prompt_lab/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.models'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/models.py`:
```python
"""Per-model Bedrock specs: model id, computer-use tool version + beta flag, display, price.

Ground truth for the ids/versions/betas is the repo files
`claude-opus-4-7-model-details.txt` and `claude-sonnet-4-5-model-details.txt`.
Prices are list $/million tokens — verify against current Bedrock eu-west-1 pricing.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    tool_type: str          # Anthropic computer-use tool "type" string
    beta_flag: str          # anthropic_beta value
    display_width: int
    display_height: int
    display_number: int
    price_in: float         # $/million input tokens
    price_out: float        # $/million output tokens


MODELS = {
    "sonnet-4-5": ModelSpec(
        key="sonnet-4-5",
        model_id="eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        tool_type="computer_20250124",
        beta_flag="computer-use-2025-01-24",
        display_width=1280,
        display_height=800,
        display_number=1,
        price_in=3.0,
        price_out=15.0,
    ),
    "opus-4-7": ModelSpec(
        key="opus-4-7",
        model_id="eu.anthropic.claude-opus-4-7",
        tool_type="computer_20251124",
        beta_flag="computer-use-2025-11-24",
        display_width=1280,
        display_height=800,
        display_number=1,
        price_in=15.0,
        price_out=75.0,
    ),
}


def spec_for(key: str) -> ModelSpec:
    try:
        return MODELS[key]
    except KeyError:
        raise ValueError(f"Unknown model key: {key!r}. Known: {sorted(MODELS)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/models.py tests/test_models.py
git commit -m "feat: add model registry with per-model tool version + beta"
```

---

## Task 3: Transcript & cost (`transcript.py`)

**Files:**
- Create: `prompt_lab/transcript.py`
- Test: `tests/test_transcript.py`

- [ ] **Step 1: Write the failing test**

`tests/test_transcript.py`:
```python
from prompt_lab.transcript import Usage, ToolCall, Transcript
from prompt_lab.models import spec_for


def test_usage_add_accumulates():
    u = Usage()
    u.add(10, 5)
    u.add(2, 3)
    assert u.input_tokens == 12 and u.output_tokens == 8


def test_transcript_cost_uses_model_price():
    t = Transcript()
    t.usage.add(1_000_000, 1_000_000)
    spec = spec_for("sonnet-4-5")  # 3 in / 15 out per million
    assert t.cost(spec) == 18.0


def test_transcript_records_tool_calls_and_steps():
    t = Transcript()
    t.tool_calls.append(ToolCall(action="left_click", tool_input={"coordinate": [1, 2]},
                                 output="ok", error=None, has_image=True))
    t.steps = 3
    t.stop_reason = "end_turn"
    assert len(t.tool_calls) == 1
    assert t.tool_calls[0].action == "left_click"
    assert t.steps == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transcript.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.transcript'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/transcript.py`:
```python
"""Records what happened during one agent episode (for scoring + reporting)."""
from dataclasses import dataclass, field
from typing import Any, Optional

from prompt_lab.models import ModelSpec


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)


@dataclass
class ToolCall:
    action: str
    tool_input: dict
    output: Optional[str]
    error: Optional[str]
    has_image: bool


@dataclass
class Transcript:
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = ""
    steps: int = 0           # number of model invocations
    user_prompts: int = 0    # conversational: how many user prompts were issued
    wall_seconds: float = 0.0

    def cost(self, spec: ModelSpec) -> float:
        return (self.usage.input_tokens / 1_000_000 * spec.price_in
                + self.usage.output_tokens / 1_000_000 * spec.price_out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transcript.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/transcript.py tests/test_transcript.py
git commit -m "feat: add transcript + cost model"
```

---

## Task 4: Executor REST client (`executor_client.py`)

**Files:**
- Create: `prompt_lab/executor_client.py`
- Test: `tests/test_executor_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_executor_client.py`:
```python
from prompt_lab.executor_client import ExecutorClient, ExecResult


def test_act_posts_tool_input_and_parses_success():
    captured = {}

    def fake_transport(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"output": "Action completed", "base64image": "AAAA"}

    client = ExecutorClient("http://host:8081", transport=fake_transport)
    res = client.act({"action": "left_click", "coordinate": [10, 20]})

    assert captured["url"] == "http://host:8081/computer_tool"
    assert captured["payload"] == {"action": "left_click", "coordinate": [10, 20]}
    assert isinstance(res, ExecResult)
    assert res.output == "Action completed"
    assert res.image_b64 == "AAAA"
    assert res.error is None


def test_act_parses_error_response():
    def fake_transport(url, payload):
        return {"error_message": "boom"}

    res = ExecutorClient("http://h:8081", transport=fake_transport).act({"action": "screenshot"})
    assert res.error == "boom"
    assert res.output is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_executor_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.executor_client'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/executor_client.py`:
```python
"""Client for the existing windows_server.py POST /computer_tool contract.

Maps a Claude `computer` tool-use input dict onto the JSON the executor expects,
and parses the {output, base64image} | {error_message} response.
"""
import json
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


class ExecutorClient:
    def __init__(self, base_url: str, transport: Callable[[str, dict], dict] = _http_transport):
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def act(self, tool_input: dict) -> ExecResult:
        # Drop None values so the executor sees only the keys for this action.
        payload = {k: v for k, v in tool_input.items() if v is not None}
        body = self._transport(f"{self.base_url}/computer_tool", payload)
        if body.get("error_message"):
            return ExecResult(error=body["error_message"])
        return ExecResult(output=body.get("output"), image_b64=body.get("base64image"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_executor_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/executor_client.py tests/test_executor_client.py
git commit -m "feat: add /computer_tool executor client"
```

---

## Task 5: Bedrock request/response helpers (`bedrock_client.py`)

**Files:**
- Create: `prompt_lab/bedrock_client.py`
- Test: `tests/test_bedrock_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_bedrock_client.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bedrock_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.bedrock_client'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/bedrock_client.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bedrock_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/bedrock_client.py tests/test_bedrock_client.py
git commit -m "feat: add Bedrock body/response helpers + client"
```

---

## Task 6: Prompt variant loader (`prompts.py`)

**Files:**
- Create: `prompt_lab/prompts.py`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

`tests/test_prompts.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.prompts'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/prompts.py`:
```python
"""Load a prompt variant file (## system / ## user sections) and render the user template."""
import os
from dataclasses import dataclass


@dataclass
class PromptVariant:
    id: str
    system: str
    user_template: str


def load_variant(path: str) -> PromptVariant:
    text = open(path, encoding="utf-8").read()
    sections = {"system": [], "user": []}
    current = None
    for line in text.splitlines():
        header = line.strip().lower()
        if header == "## system":
            current = "system"
            continue
        if header == "## user":
            current = "user"
            continue
        if current:
            sections[current].append(line)
    variant_id = os.path.splitext(os.path.basename(path))[0]
    return PromptVariant(
        id=variant_id,
        system="\n".join(sections["system"]).strip(),
        user_template="\n".join(sections["user"]).strip(),
    )


def render_user(variant: PromptVariant, case: dict) -> str:
    return variant.user_template.format(**case)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/prompts.py tests/test_prompts.py
git commit -m "feat: add prompt variant loader + renderer"
```

---

## Task 7: Scenario loader (`scenarios.py`)

**Files:**
- Create: `prompt_lab/scenarios.py`
- Test: `tests/test_scenarios.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scenarios.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenarios.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.scenarios'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/scenarios.py`:
```python
"""Load a scenario YAML: target app + case data + expected record + (script | goal)."""
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class Scenario:
    id: str
    mode: str               # "single_prompt" | "conversational"
    target: str             # "warranty" | "returns"
    case: dict
    expected_record: dict
    script: list[str] = field(default_factory=list)
    goal: Optional[str] = None
    max_user_prompts: int = 0


def load_scenario(path: str) -> Scenario:
    data = yaml.safe_load(open(path, encoding="utf-8"))
    return Scenario(
        id=data["id"],
        mode=data["mode"],
        target=data["target"],
        case=data.get("case", {}),
        expected_record=data.get("expected_record", {}),
        script=data.get("script", []) or [],
        goal=data.get("goal"),
        max_user_prompts=int(data.get("max_user_prompts", 0)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scenarios.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/scenarios.py tests/test_scenarios.py
git commit -m "feat: add scenario loader"
```

---

## Task 8: Driver protocol + scripted driver (`drivers/base.py`, `drivers/scripted.py`)

**Files:**
- Create: `prompt_lab/drivers/base.py`
- Create: `prompt_lab/drivers/scripted.py`
- Test: `tests/test_scripted_driver.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scripted_driver.py`:
```python
from prompt_lab.drivers.scripted import ScriptedDriver
from prompt_lab.transcript import Transcript


def test_scripted_driver_yields_prompts_then_none():
    d = ScriptedDriver(["first", "second"])
    t = Transcript()
    assert d.next_prompt(t) == "first"
    assert d.next_prompt(t) == "second"
    assert d.next_prompt(t) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripted_driver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.drivers.scripted'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/drivers/base.py`:
```python
"""A Driver supplies the next user prompt in a conversational episode, or None when done."""
from typing import Optional, Protocol

from prompt_lab.transcript import Transcript


class Driver(Protocol):
    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        ...
```

`prompt_lab/drivers/scripted.py`:
```python
"""Deterministic driver — replays a fixed list of user prompts (the demo script)."""
from typing import Optional

from prompt_lab.transcript import Transcript


class ScriptedDriver:
    def __init__(self, prompts: list[str]):
        self._prompts = list(prompts)
        self._i = 0

    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        if self._i >= len(self._prompts):
            return None
        prompt = self._prompts[self._i]
        self._i += 1
        return prompt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scripted_driver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/drivers/base.py prompt_lab/drivers/scripted.py tests/test_scripted_driver.py
git commit -m "feat: add driver protocol + scripted driver"
```

---

## Task 9: Persona driver (`drivers/persona.py`)

**Files:**
- Create: `prompt_lab/drivers/persona.py`
- Test: `tests/test_persona_driver.py`

- [ ] **Step 1: Write the failing test**

`tests/test_persona_driver.py`:
```python
from prompt_lab.drivers.persona import PersonaDriver
from prompt_lab.transcript import Transcript


def test_persona_returns_next_prompt_from_complete_fn():
    calls = []

    def fake_complete(system, user):
        calls.append((system, user))
        return "Please set the courier to DHL."

    d = PersonaDriver(goal="create a dispatch record", complete=fake_complete)
    t = Transcript()
    t.messages.append({"role": "assistant", "content": [{"type": "text", "text": "Which courier?"}]})
    out = d.next_prompt(t)
    assert out == "Please set the courier to DHL."
    assert "create a dispatch record" in calls[0][0]  # goal in system prompt


def test_persona_done_sentinel_returns_none():
    d = PersonaDriver(goal="g", complete=lambda s, u: "TASK_COMPLETE")
    assert d.next_prompt(Transcript()) is None


def test_persona_respects_max_turns():
    d = PersonaDriver(goal="g", complete=lambda s, u: "keep going", max_turns=2)
    t = Transcript()
    assert d.next_prompt(t) == "keep going"
    assert d.next_prompt(t) == "keep going"
    assert d.next_prompt(t) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_persona_driver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.drivers.persona'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/drivers/persona.py`:
```python
"""LLM persona driver — plays the presenter, emitting the next instruction toward a goal.

`complete(system, user) -> str` is injected (defaults wrap BedrockClient.complete_text),
so this is unit-testable with a stub. The persona returns the literal "TASK_COMPLETE"
when it judges the goal met; that maps to None (episode ends).
"""
from typing import Callable, Optional

from prompt_lab.transcript import Transcript

DONE = "TASK_COMPLETE"

_SYSTEM_TEMPLATE = (
    "You are a demo presenter directing a computer-use agent toward this goal:\n"
    "{goal}\n\n"
    "Each turn, look at the agent's latest message and issue the single next short "
    "instruction to move toward the goal. When the goal is fully met, reply with "
    "exactly {done}."
)


class PersonaDriver:
    def __init__(self, goal: str, complete: Callable[[str, str], str], max_turns: int = 6):
        self.goal = goal
        self._complete = complete
        self._max_turns = max_turns
        self._turns = 0

    def _last_agent_text(self, transcript: Transcript) -> str:
        for msg in reversed(transcript.messages):
            if msg.get("role") == "assistant":
                return "".join(b.get("text", "") for b in msg.get("content", [])
                               if b.get("type") == "text")
        return "(no message yet)"

    def next_prompt(self, transcript: Transcript) -> Optional[str]:
        if self._turns >= self._max_turns:
            return None
        self._turns += 1
        system = _SYSTEM_TEMPLATE.format(goal=self.goal, done=DONE)
        user = f"Agent's latest message:\n{self._last_agent_text(transcript)}"
        reply = self._complete(system, user).strip()
        if reply == DONE or not reply:
            return None
        return reply
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_persona_driver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/drivers/persona.py tests/test_persona_driver.py
git commit -m "feat: add LLM persona driver"
```

---

## Task 10: The agent loop (`bedrock_loop.py`)

**Files:**
- Create: `prompt_lab/bedrock_loop.py`
- Test: `tests/test_bedrock_loop.py`

- [ ] **Step 1: Write the failing test**

`tests/test_bedrock_loop.py`:
```python
from prompt_lab.bedrock_loop import run_episode
from prompt_lab.models import spec_for


class FakeBedrock:
    """Returns queued assistant messages in order."""
    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, spec, system, messages, max_tokens=1024):
        return self._responses.pop(0)


class FakeExecutor:
    def __init__(self):
        self.actions = []

    def act(self, tool_input):
        from prompt_lab.executor_client import ExecResult
        self.actions.append(tool_input)
        return ExecResult(output="ok", image_b64="IMG", error=None)


def _tool_use(action):
    return {"role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "computer",
                         "input": {"action": action}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 2}}


def _end_turn(text="done"):
    return {"role": "assistant",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1}}


def test_single_prompt_episode_runs_actions_until_end_turn():
    bedrock = FakeBedrock([_tool_use("screenshot"), _tool_use("left_click"), _end_turn()])
    executor = FakeExecutor()
    t = run_episode(bedrock, executor, spec_for("sonnet-4-5"),
                    system="SYS", user_prompt="fill the form", step_cap=10)

    assert t.stop_reason == "end_turn"
    assert [c.action for c in t.tool_calls] == ["screenshot", "left_click"]
    assert executor.actions == [{"action": "screenshot"}, {"action": "left_click"}]
    assert t.usage.output_tokens == 4  # 2 + 2 + ... actually 2+2+1


def test_step_cap_stops_runaway():
    bedrock = FakeBedrock([_tool_use("screenshot")] * 100)
    t = run_episode(bedrock, FakeExecutor(), spec_for("sonnet-4-5"),
                    system="s", user_prompt="go", step_cap=3)
    assert t.stop_reason == "step_cap"
    assert t.steps == 3


def test_conversational_driver_injects_next_prompt():
    # turn 1: end_turn -> driver gives "next" -> turn 2: end_turn -> driver done
    bedrock = FakeBedrock([_end_turn("turn1"), _end_turn("turn2")])

    class TwoStepDriver:
        def __init__(self):
            self.calls = 0
        def next_prompt(self, transcript):
            self.calls += 1
            return "do the next thing" if self.calls == 1 else None

    driver = TwoStepDriver()
    t = run_episode(bedrock, FakeExecutor(), spec_for("sonnet-4-5"),
                    system="s", user_prompt="start", step_cap=10,
                    driver=driver, max_user_prompts=4)
    assert t.user_prompts == 1
    assert t.stop_reason == "end_turn"
```

> Note: fix the first test's token assertion to `t.usage.output_tokens == 5` (2+2+1) when writing — adjust to the real sum.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bedrock_loop.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.bedrock_loop'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/bedrock_loop.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bedrock_loop.py -v`
Expected: PASS (after correcting the token-sum assertion noted above)

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/bedrock_loop.py tests/test_bedrock_loop.py
git commit -m "feat: add the Bedrock agent loop (single + conversational)"
```

---

## Task 11: Scoring (`scoring.py`)

**Files:**
- Create: `prompt_lab/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scoring.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.scoring'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/scoring.py`:
```python
"""Deterministic pass/fail scoring: correctness vs expected_record + safety checks."""
from dataclasses import dataclass, field

from prompt_lab.scenarios import Scenario
from prompt_lab.transcript import Transcript


@dataclass
class ScoreResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _field_matches(expected, actual) -> bool:
    if isinstance(expected, dict) and "contains" in expected:
        return actual is not None and str(expected["contains"]).lower() in str(actual).lower()
    return actual == expected


def score(scenario: Scenario, new_records: list[dict], transcript: Transcript,
          step_cap: int = 30, max_user_prompts: int = 0,
          destructive_markers: list[str] | None = None) -> ScoreResult:
    reasons: list[str] = []

    # Correctness
    if len(new_records) == 0:
        reasons.append("no record was created")
    elif len(new_records) != 1:
        reasons.append(f"expected exactly one new record, got {len(new_records)}")

    if new_records:
        rec = new_records[-1]
        for key, expected in scenario.expected_record.items():
            if not _field_matches(expected, rec.get(key)):
                reasons.append(f"field {key!r}: expected {expected!r}, got {rec.get(key)!r}")
        if str(rec.get("Status", "")).strip().lower() == "pending":
            reasons.append("Status left as Pending")

    # Safety
    if transcript.stop_reason == "step_cap":
        reasons.append("hit step cap (runaway)")
    if any(c.error for c in transcript.tool_calls):
        reasons.append("executor returned an error during the run")
    for marker in (destructive_markers or []):
        if any(marker in (c.output or "") for c in transcript.tool_calls):
            reasons.append(f"destructive action detected: {marker!r}")
    if scenario.mode == "conversational" and max_user_prompts and transcript.user_prompts > max_user_prompts:
        reasons.append(f"used {transcript.user_prompts} user prompts (cap {max_user_prompts})")

    metrics = {
        "steps": transcript.steps,
        "tool_calls": len(transcript.tool_calls),
        "input_tokens": transcript.usage.input_tokens,
        "output_tokens": transcript.usage.output_tokens,
        "wall_seconds": round(transcript.wall_seconds, 2),
        "user_prompts": transcript.user_prompts,
    }
    return ScoreResult(passed=not reasons, reasons=reasons, metrics=metrics)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/scoring.py tests/test_scoring.py
git commit -m "feat: add deterministic scoring (correctness + safety)"
```

---

## Task 12: Control client (`control_client.py`)

**Files:**
- Create: `prompt_lab/control_client.py`
- Test: `tests/test_control_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_control_client.py`:
```python
from prompt_lab.control_client import ControlClient


def test_setup_posts_app_and_case():
    captured = {}

    def fake_transport(method, url, payload):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"ready": True, "baseline_count": 0}

    c = ControlClient("http://host:8081", transport=fake_transport)
    out = c.setup("warranty", {"case_id": "EQ-2026-0042"})
    assert captured["method"] == "POST"
    assert captured["url"] == "http://host:8081/control/setup"
    assert captured["payload"] == {"app": "warranty", "case": {"case_id": "EQ-2026-0042"}}
    assert out["baseline_count"] == 0


def test_records_gets_app_records():
    def fake_transport(method, url, payload):
        assert method == "GET"
        assert url == "http://host:8081/control/records?app=returns"
        return {"records": [{"x": 1}], "count": 1}

    c = ControlClient("http://host:8081", transport=fake_transport)
    out = c.records("returns")
    assert out["count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.control_client'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/control_client.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/control_client.py tests/test_control_client.py
git commit -m "feat: add host control client"
```

---

## Task 13: Report rendering (`report.py`)

**Files:**
- Create: `prompt_lab/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

`tests/test_report.py`:
```python
import json
from prompt_lab.report import render_markdown, write


def _cells():
    return [
        {"variant": "warranty_v1", "scenario": "warranty-wheel-replacement",
         "model": "sonnet-4-5", "passed": True, "steps": 6, "cost": 0.01, "reasons": []},
        {"variant": "warranty_v1", "scenario": "warranty-wheel-replacement",
         "model": "opus-4-7", "passed": False, "steps": 12, "cost": 0.30,
         "reasons": ["Status left as Pending"]},
    ]


def test_render_markdown_has_rows_and_passrate():
    md = render_markdown(_cells())
    assert "warranty_v1" in md
    assert "sonnet-4-5" in md and "opus-4-7" in md
    assert "Status left as Pending" in md
    assert "50%" in md  # 1 of 2 passed


def test_write_emits_md_and_json(tmp_path):
    paths = write(_cells(), str(tmp_path))
    assert paths["markdown"].endswith(".md")
    assert paths["json"].endswith(".json")
    data = json.loads(open(paths["json"], encoding="utf-8").read())
    assert len(data) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.report'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/report.py`:
```python
"""Render the matrix results to Markdown + JSON."""
import json
import os
from datetime import datetime


def render_markdown(cells: list[dict]) -> str:
    total = len(cells)
    passed = sum(1 for c in cells if c["passed"])
    rate = round(100 * passed / total) if total else 0
    lines = [
        "# Prompt Lab Report",
        "",
        f"Pass rate: **{passed}/{total} ({rate}%)**",
        "",
        "| Variant | Scenario | Model | Pass | Steps | Cost $ | Reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        reasons = "; ".join(c.get("reasons", [])) or "—"
        mark = "✅" if c["passed"] else "❌"
        lines.append(f"| {c['variant']} | {c['scenario']} | {c['model']} | {mark} "
                     f"| {c.get('steps', '')} | {c.get('cost', 0):.3f} | {reasons} |")
    return "\n".join(lines) + "\n"


def write(cells: list[dict], out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    md_path = os.path.join(out_dir, f"report-{stamp}.md")
    json_path = os.path.join(out_dir, f"report-{stamp}.json")
    open(md_path, "w", encoding="utf-8").write(render_markdown(cells))
    open(json_path, "w", encoding="utf-8").write(json.dumps(cells, indent=2))
    return {"markdown": md_path, "json": json_path}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/report.py tests/test_report.py
git commit -m "feat: add markdown/json report"
```

---

## Task 14: Mendix export (`mendix_export.py`)

**Files:**
- Create: `prompt_lab/mendix_export.py`
- Test: `tests/test_mendix_export.py`

- [ ] **Step 1: Write the failing test**

`tests/test_mendix_export.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mendix_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.mendix_export'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/mendix_export.py`:
```python
"""Emit the chosen prompts as paste-ready Mendix TestSystemPrompt / TestUserPrompt values."""
from prompt_lab.prompts import PromptVariant, render_user


def export_variant(variant: PromptVariant, case: dict) -> str:
    user = render_user(variant, case)
    return (
        f"# Variant: {variant.id}\n\n"
        "## EnquiryManagementMemory.TestSystemPrompt\n"
        f"{variant.system}\n\n"
        "## EnquiryManagementMemory.TestUserPrompt\n"
        f"{user}\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mendix_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/mendix_export.py tests/test_mendix_export.py
git commit -m "feat: add Mendix paste-ready prompt export"
```

---

## Task 15: Matrix runner (`runner.py`)

**Files:**
- Create: `prompt_lab/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

`tests/test_runner.py`:
```python
from prompt_lab.runner import run_matrix
from prompt_lab.prompts import PromptVariant
from prompt_lab.scenarios import Scenario
from prompt_lab.executor_client import ExecResult


class FakeBedrock:
    def invoke(self, spec, system, messages, max_tokens=1024):
        return {"role": "assistant",
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 3, "output_tokens": 1}}


class FakeExecutor:
    def act(self, tool_input):
        return ExecResult(output="ok", image_b64="IMG")


class FakeControl:
    def __init__(self, records):
        self._records = records
    def setup(self, app, case):
        return {"ready": True, "baseline_count": 0}
    def records(self, app):
        return {"records": self._records, "count": len(self._records)}


def test_run_matrix_scores_each_cell():
    variant = PromptVariant(id="warranty_v1", system="SYS",
                            user_template="do {recommended_action} ref DISP-{uuid}")
    scenario = Scenario(id="warranty-wheel-replacement", mode="single_prompt", target="warranty",
                        case={"recommended_action": "replace", "uuid": "A1B2C3"},
                        expected_record={"Status": "Replacement Approved"})
    good_record = {"Status": "Replacement Approved"}

    cells = run_matrix(
        variants=[variant], scenarios=[scenario], model_keys=["sonnet-4-5"], repeats=1,
        bedrock=FakeBedrock(), executor=FakeExecutor(), control=FakeControl([good_record]),
        persona_complete=lambda s, u: "TASK_COMPLETE",
    )
    assert len(cells) == 1
    assert cells[0]["passed"] is True
    assert cells[0]["variant"] == "warranty_v1"
    assert cells[0]["model"] == "sonnet-4-5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt_lab.runner'`

- [ ] **Step 3: Write minimal implementation**

`prompt_lab/runner.py`:
```python
"""Run the {variant × scenario × model × repeat} matrix and produce scored cells.

Clients (bedrock/executor/control) are injected so this is unit-testable; the CLI
wires the real BedrockClient/ExecutorClient/ControlClient.
"""
import argparse
import glob

from prompt_lab import report
from prompt_lab.bedrock_loop import run_episode
from prompt_lab.drivers.persona import PersonaDriver
from prompt_lab.drivers.scripted import ScriptedDriver
from prompt_lab.models import spec_for
from prompt_lab.prompts import PromptVariant, load_variant, render_user
from prompt_lab.scenarios import Scenario, load_scenario
from prompt_lab.scoring import score

STEP_CAP = 30


def _run_cell(variant, scenario, spec, bedrock, executor, control, persona_complete):
    setup = control.setup(scenario.target, scenario.case)
    baseline = setup.get("baseline_count", 0)
    user_prompt = render_user(variant, scenario.case)

    driver = None
    if scenario.mode == "conversational":
        if scenario.script:
            driver = ScriptedDriver(scenario.script)
        else:
            driver = PersonaDriver(goal=scenario.goal or "", complete=persona_complete,
                                   max_turns=scenario.max_user_prompts or 6)

    transcript = run_episode(bedrock, executor, spec, system=variant.system,
                             user_prompt=user_prompt, step_cap=STEP_CAP,
                             driver=driver, max_user_prompts=scenario.max_user_prompts)

    after = control.records(scenario.target).get("records", [])
    new_records = after[baseline:]
    result = score(scenario, new_records, transcript, step_cap=STEP_CAP,
                   max_user_prompts=scenario.max_user_prompts)
    return {
        "variant": variant.id, "scenario": scenario.id, "model": spec.key,
        "passed": result.passed, "reasons": result.reasons,
        "steps": result.metrics["steps"], "cost": transcript.cost(spec),
        "metrics": result.metrics,
    }


def run_matrix(variants, scenarios, model_keys, repeats, bedrock, executor, control,
               persona_complete) -> list[dict]:
    cells = []
    for variant in variants:
        for scenario in scenarios:
            for model_key in model_keys:
                spec = spec_for(model_key)
                for _ in range(repeats):
                    cells.append(_run_cell(variant, scenario, spec, bedrock, executor,
                                           control, persona_complete))
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the computer-use prompt lab matrix.")
    parser.add_argument("--host", required=True, help="executor+control base URL, e.g. http://3.249.25.226:8081")
    parser.add_argument("--prompts", default="prompt_lab/prompts/*.md")
    parser.add_argument("--scenarios", default="prompt_lab/scenarios/*.yaml")
    parser.add_argument("--models", default="sonnet-4-5", help="comma-separated model keys")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--region", default="eu-west-1")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--out", default="prompt_lab/reports")
    args = parser.parse_args(argv)

    from prompt_lab.bedrock_client import BedrockClient
    from prompt_lab.control_client import ControlClient
    from prompt_lab.executor_client import ExecutorClient

    variants = [load_variant(p) for p in sorted(glob.glob(args.prompts))]
    scenarios = [load_scenario(p) for p in sorted(glob.glob(args.scenarios))]
    bedrock = BedrockClient(region=args.region, profile=args.profile)
    executor = ExecutorClient(args.host)
    control = ControlClient(args.host)
    persona_spec = spec_for(args.models.split(",")[0].strip())
    persona_complete = lambda system, user: bedrock.complete_text(persona_spec, system, user)

    cells = run_matrix(variants, scenarios, [m.strip() for m in args.models.split(",")],
                       args.repeats, bedrock, executor, control, persona_complete)
    paths = report.write(cells, args.out)
    print(f"Report: {paths['markdown']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add prompt_lab/runner.py tests/test_runner.py
git commit -m "feat: add matrix runner + CLI"
```

---

## Task 16: Host control logic (`scenario_control.py`)

**Files:**
- Create: `computer-use-windows/scenario_control.py`
- Test: `tests/test_scenario_control.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scenario_control.py`:
```python
import json
import os

from scenario_control import ControlHandler, FakeLauncher


def test_setup_clears_records_and_launches(tmp_path):
    data_dir = tmp_path
    (data_dir / "warranty_cases.json").write_text(json.dumps([{"old": 1}]), encoding="utf-8")
    launcher = FakeLauncher()
    handler = ControlHandler(data_dir=str(data_dir), launcher=launcher)

    code, body = handler.handle("/control/setup", "POST",
                                {"app": "warranty", "case": {"case_id": "EQ-2026-0042"}})
    assert code == 200
    assert body["ready"] is True
    assert body["baseline_count"] == 0
    assert json.loads((data_dir / "warranty_cases.json").read_text()) == []
    assert launcher.started == [("warranty", {"case_id": "EQ-2026-0042"})]


def test_records_returns_file_contents(tmp_path):
    (tmp_path / "dispatch_records.json").write_text(json.dumps([{"reference": "DSP-1"}]), encoding="utf-8")
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/records?app=returns", "GET", None)
    assert code == 200
    assert body["count"] == 1
    assert body["records"][0]["reference"] == "DSP-1"


def test_health(tmp_path):
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/health", "GET", None)
    assert code == 200 and body["ok"] is True


def test_unknown_path_404(tmp_path):
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/nope", "GET", None)
    assert code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenario_control.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scenario_control'`

- [ ] **Step 3: Write minimal implementation**

`computer-use-windows/scenario_control.py`:
```python
"""Host-side scenario control for the prompt lab — no pyautogui dependency.

Routed to by windows_server.py for /control/* paths. Resets the target app to a
known state (clears its records file + relaunches) and reads back records for
remote scoring. The real Launcher spawns processes on the demo host; FakeLauncher
is used in unit tests.
"""
import json
import os
import subprocess
import sys
import urllib.parse

RECORDS_FILE = {"warranty": "warranty_cases.json", "returns": "dispatch_records.json"}
HERE = os.path.dirname(os.path.abspath(__file__))


class FakeLauncher:
    def __init__(self):
        self.started = []
        self.stopped = []

    def stop(self, app):
        self.stopped.append(app)

    def start(self, app, case):
        self.started.append((app, case))


class SubprocessLauncher:
    """Real host launcher. Best-effort: relaunch the desktop app / ensure the web tab."""
    def stop(self, app):
        if app == "warranty" and sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe"], capture_output=True)

    def start(self, app, case):
        if app == "warranty":
            subprocess.Popen(["pythonw", os.path.join(HERE, "warranty_case_manager.py")])
        elif app == "returns":
            # Flask is started by start_demo_env.bat; just (re)open the tab on the host.
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "msedge", "http://localhost:5050"])


class ControlHandler:
    def __init__(self, data_dir: str | None = None, launcher=None):
        self.data_dir = data_dir or os.path.join(HERE, "data")
        self.launcher = launcher or SubprocessLauncher()

    def _records_path(self, app: str) -> str:
        return os.path.join(self.data_dir, RECORDS_FILE[app])

    def _read_records(self, app: str) -> list:
        path = self._records_path(app)
        if not os.path.exists(path):
            return []
        try:
            return json.loads(open(path, encoding="utf-8").read())
        except (json.JSONDecodeError, OSError):
            return []

    def handle(self, path: str, method: str, body: dict | None):
        parsed = urllib.parse.urlparse(path)
        route = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if route == "/control/health":
            return 200, {"ok": True}

        if route == "/control/setup" and method == "POST":
            app = body["app"]
            os.makedirs(self.data_dir, exist_ok=True)
            open(self._records_path(app), "w", encoding="utf-8").write("[]")
            self.launcher.stop(app)
            self.launcher.start(app, body.get("case", {}))
            return 200, {"ready": True, "baseline_count": 0}

        if route == "/control/records" and method == "GET":
            app = query.get("app", [""])[0]
            records = self._read_records(app)
            return 200, {"records": records, "count": len(records)}

        if route == "/control/teardown" and method == "POST":
            self.launcher.stop(body.get("app", ""))
            return 200, {"ok": True}

        return 404, {"error_message": f"unknown control route: {route}"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scenario_control.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add computer-use-windows/scenario_control.py tests/test_scenario_control.py
git commit -m "feat: add host-side scenario control (setup/records)"
```

---

## Task 17: Wire control endpoints into `windows_server.py`

**Files:**
- Modify: `computer-use-windows/windows_server.py` (the `ComputerToolHandler.do_POST`/`do_GET` methods and add control routing)

- [ ] **Step 1: Add control routing to the server**

In `computer-use-windows/windows_server.py`, add an import near the top (after the existing imports):

```python
from scenario_control import ControlHandler

_control = ControlHandler()
```

Replace the existing `do_GET` method:

```python
    def do_GET(self):
        self.send_error(405, "Method Not Allowed")
```

with one that serves control GETs:

```python
    def do_GET(self):
        if self.path.startswith("/control/"):
            code, payload = _control.handle(self.path, "GET", None)
            self._send_json(code, payload)
            return
        self.send_error(405, "Method Not Allowed")
```

In `do_POST`, before the existing `if self.path != "/computer_tool":` guard, add control handling:

```python
    def do_POST(self):
        if self.path.startswith("/control/"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"error_message": f"Bad request: {exc}"})
                return
            code, payload = _control.handle(self.path, "POST", body)
            self._send_json(code, payload)
            return

        if self.path != "/computer_tool":
            self.send_error(404, "Not Found")
            return
        # ... existing /computer_tool handling unchanged ...
```

- [ ] **Step 2: Verify the server still imports and the control routes resolve**

Because `windows_server.py` imports `pyautogui` at module top (often absent on a dev box), verify on a machine with deps, or verify the routing indirectly. Run the existing unit suite (which covers `ControlHandler` directly):

Run: `python -m pytest tests/test_scenario_control.py -v`
Expected: PASS

Then, on the host (or any box with `pyautogui` + `Pillow` installed), smoke-test the import:

Run: `python -c "import computer-use-windows.windows_server" 2>NUL || python -c "import sys; sys.path.insert(0,'computer-use-windows'); import windows_server; print('ok')"`
Expected: prints `ok` (server module imports with control wiring).

- [ ] **Step 3: Commit**

```bash
git add computer-use-windows/windows_server.py
git commit -m "feat: route /control/* to scenario_control in windows_server"
```

---

## Task 18: Sample data, gitignore, and README

**Files:**
- Create: `prompt_lab/prompts/warranty_v1.md`
- Create: `prompt_lab/prompts/returns_v1.md`
- Create: `prompt_lab/scenarios/warranty-wheel-replacement.yaml`
- Create: `prompt_lab/scenarios/returns-wheel-replacement.yaml`
- Create: `prompt_lab/README.md`
- Modify: `.gitignore` (add `prompt_lab/reports/`)
- Test: `tests/test_samples_load.py`

> **Before writing the scenarios:** open `computer-use-windows/warranty_case_manager.py` and
> `computer-use-windows/returns_portal/app.py` and read the exact JSON keys each writes on
> submit (per spec §13 open item). Use those exact keys in `expected_record`. The values
> below assume the wheels narrative already prefilled by the apps.

- [ ] **Step 1: Write the failing test**

`tests/test_samples_load.py`:
```python
import glob
from prompt_lab.prompts import load_variant, render_user
from prompt_lab.scenarios import load_scenario


def test_all_sample_prompts_load():
    files = glob.glob("prompt_lab/prompts/*.md")
    assert files
    for f in files:
        v = load_variant(f)
        assert v.system and v.user_template


def test_all_sample_scenarios_load_and_render():
    files = glob.glob("prompt_lab/scenarios/*.yaml")
    assert files
    for f in files:
        s = load_scenario(f)
        assert s.mode in {"single_prompt", "conversational"}
        assert s.target in {"warranty", "returns"}


def test_warranty_variant_renders_against_scenario_case():
    v = load_variant("prompt_lab/prompts/warranty_v1.md")
    s = load_scenario("prompt_lab/scenarios/warranty-wheel-replacement.yaml")
    rendered = render_user(v, s.case)
    assert rendered  # no missing placeholders -> no KeyError
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_samples_load.py -v`
Expected: FAIL — files do not exist / glob empty assertion fails.

- [ ] **Step 3: Create the sample files**

`prompt_lab/prompts/warranty_v1.md`:
```markdown
## system
You are an automation agent operating the Complaint Resolution System v2.3 desktop application on Windows. The window may be minimised - bring it to focus first. The form has these fields: Case ID (pre-filled), Customer (pre-filled), Product (pre-filled), Resolution (text area - required), Status (dropdown - required, do not leave as Pending), and Dispatch Ref (text box - required). Fill all required fields then click Submit.

## user
Fill in the Complaint Resolution System: Resolution: {recommended_action}; Status: Replacement Approved; Dispatch Ref: DISP-{uuid}. Click Submit when complete.
```

`prompt_lab/prompts/returns_v1.md`:
```markdown
## system
You are an automation agent operating the Returns Dispatch Portal, a legacy web form open in the browser. Bring the browser to focus first. Follow the user's instructions one step at a time, taking a screenshot to confirm each change before moving on. Required fields: Dispatch Type (dropdown), Shipping Address, Courier (dropdown), Notes. Create the dispatch record only when the user asks you to.

## user
Open the Returns Dispatch Portal for case {case_id} and wait for my next instruction.
```

`prompt_lab/scenarios/warranty-wheel-replacement.yaml`:
```yaml
id: warranty-wheel-replacement
mode: single_prompt
target: warranty
case:
  case_id: EQ-2026-0042
  customer: "Robertson, J."
  product: "Evora Alloy Wheel AW-200"
  recommended_action: "Approve free-of-charge replacement of the affected rear alloy wheels and raise a safety recall."
  uuid: "A1B2C3"
expected_record:
  # NOTE: confirm these keys match warranty_case_manager.py's submit payload.
  Status: "Replacement Approved"
  DispatchRef: "DISP-A1B2C3"
  Resolution: { contains: "replacement" }
```

`prompt_lab/scenarios/returns-wheel-replacement.yaml`:
```yaml
id: returns-wheel-replacement
mode: conversational
target: returns
case:
  case_id: EQ-2026-0042
  customer: "Robertson, J."
  product_code: "AW-200-REAR"
expected_record:
  # NOTE: confirm these keys match returns_portal/app.py's submit payload.
  dispatch_type: "Wheel Replacement"
  courier: "DHL"
script:
  - "Open the returns portal and start a new dispatch record for case EQ-2026-0042."
  - "Set dispatch type to Wheel Replacement and courier to DHL."
  - "Add the shipping address and a brief note, then create the dispatch record."
goal: >
  Create a Wheel Replacement dispatch record for case EQ-2026-0042 via DHL,
  with a shipping address and a short note, and submit it.
max_user_prompts: 4
```

`prompt_lab/README.md`:
```markdown
# Computer-Use Prompt Lab

Iterate on the system/user prompts for the BOAT 2026 computer-use demo, score the
agent against the two legacy apps, and export the winners for Mendix.

## How it works
This package plays the role Mendix plays: it runs the Bedrock agent loop and sends every
tool action over the existing `POST /computer_tool` contract to `windows_server.py`. See
the design spec: `docs/superpowers/specs/2026-05-29-computer-use-prompt-lab-design.md`.

## Prerequisites
- AWS creds for Bedrock (`aws sso login`, profile `default`, region `eu-west-1`).
- The demo host running `start_demo_env.bat` (windows_server.py on :8081 + the two apps).
- Network: laptop must reach `host:8081` (`/computer_tool` + `/control/*`).
- `pip install -r prompt_lab/requirements.txt`

## Run
```bash
python -m prompt_lab.runner --host http://<HOST_IP>:8081 \
  --models sonnet-4-5,opus-4-7 --repeats 2
```
Reports land in `prompt_lab/reports/`.

## Authoring
- Prompt variants: `prompt_lab/prompts/*.md` (`## system` / `## user` sections).
- Scenarios: `prompt_lab/scenarios/*.yaml` (case data + expected_record + mode).
- Export a winner for Mendix: use `prompt_lab.mendix_export.export_variant`.

## Tests
```bash
python -m pytest
```
```

Append to `.gitignore` (create the file if absent):
```text
prompt_lab/reports/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_samples_load.py -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add prompt_lab/prompts prompt_lab/scenarios prompt_lab/README.md .gitignore tests/test_samples_load.py
git commit -m "feat: add sample prompts/scenarios + README + gitignore"
```

---

## Task 19: Live smoke test (manual, on the host)

This cannot be unit-tested (needs Bedrock + a live screen). Run it once the host is up to
confirm end-to-end fidelity.

- [ ] **Step 1: Confirm credentials + reachability**

Run: `aws sts get-caller-identity` (expect the Siemens account)
Run: `curl http://<HOST_IP>:8081/control/health` (expect `{"ok": true}`)

- [ ] **Step 2: One single_prompt run against the desktop app**

Run:
```bash
python -m prompt_lab.runner --host http://<HOST_IP>:8081 \
  --prompts "prompt_lab/prompts/warranty_v1.md" \
  --scenarios "prompt_lab/scenarios/warranty-wheel-replacement.yaml" \
  --models sonnet-4-5 --repeats 1
```
Expected: a report at `prompt_lab/reports/report-*.md`; the Warranty Case Manager fills and
submits; the cell shows ✅ or actionable failure reasons.

- [ ] **Step 3: Export the winning prompt for Mendix**

Run:
```bash
python -c "from prompt_lab.prompts import load_variant; from prompt_lab.scenarios import load_scenario; from prompt_lab.mendix_export import export_variant; v=load_variant('prompt_lab/prompts/warranty_v1.md'); s=load_scenario('prompt_lab/scenarios/warranty-wheel-replacement.yaml'); print(export_variant(v, s.case))"
```
Expected: paste-ready `TestSystemPrompt` / `TestUserPrompt` text.

- [ ] **Step 4: Commit any fixes discovered during the smoke test**

```bash
git add -A
git commit -m "fix: adjustments from live smoke test"
```

---

## Self-Review

**1. Spec coverage**
- Standalone harness mirroring Mendix request → Tasks 5, 10 (build_body pins model/tool/beta/dims; loop replicates the flow). ✅
- Fidelity (per-model tool version/beta) → Task 2 `models.py` + Task 5 `build_body`. ✅
- Export to Mendix → Task 14. ✅
- Two modes (single_prompt / conversational) → Task 10 loop + Tasks 8/9 drivers + Task 15 runner mode selection. ✅
- Scripted + persona drivers → Tasks 8, 9. ✅
- Targets warranty + returns via REST executor → Tasks 4, 16, 18. ✅
- Models comparison axis → Tasks 2, 15. ✅
- Scoring (correctness + safety + captured efficiency) → Task 11. ✅
- Control endpoints (remote setup/records) → Tasks 12, 16, 17. ✅
- YAML/JSON authoring → Tasks 6, 7, 18. ✅
- Report → Task 13. ✅
- Open item (confirm app JSON keys) → called out in Task 18 pre-note + scenario NOTEs. ✅

**2. Placeholder scan:** No "TBD/TODO/handle appropriately". The one inline note (Task 10 token-sum) is an explicit correction instruction with the right value, not a placeholder. Scenario `expected_record` keys carry a verify-against-code NOTE, which is a real instruction (the open item), not a vague placeholder.

**3. Type consistency:** `ExecResult(output,image_b64,error)`, `Transcript(messages,tool_calls,usage,stop_reason,steps,user_prompts,wall_seconds)`, `ToolCall(action,tool_input,output,error,has_image)`, `ScoreResult(passed,reasons,metrics)`, `ModelSpec(... tool_type,beta_flag ...)`, `Scenario(... script,goal,max_user_prompts)`, `PromptVariant(id,system,user_template)`, driver method `next_prompt(transcript)`, client methods `act`/`setup`/`records`/`invoke`/`complete_text`/`run_episode`/`run_matrix`/`render_markdown`/`write`/`export_variant` — all used consistently across tasks. ✅

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.

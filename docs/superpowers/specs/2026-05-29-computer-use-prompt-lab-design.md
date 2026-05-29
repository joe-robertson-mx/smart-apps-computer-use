# Computer-Use Prompt Lab — Design

- **Date:** 2026-05-29
- **Status:** approved (design); pending implementation plan
- **Repo:** `smart-apps-computer-use`
- **Owner:** Joe Robertson

## 1. Context & problem

The BOAT 2026 demo includes a **computer-use beat** (Storyboard Step 13–14). After a
manager approves a warranty resolution, a Mendix workflow invokes a bounded
computer-use agent to write the outcome into two legacy systems that have no API:

1. A legacy **desktop** app — *Warranty Case Manager* ("Complaint Resolution System v2.3", tkinter).
2. A legacy **web portal** — *Returns Dispatch Portal* (Flask, `localhost:5050`).

The agent runs as Bedrock Claude inside Mendix (`AmazonBedrockConnector` +
`GenAICommons.ChatCompletions_WithoutHistory`), driven by a **system prompt** and a
**user prompt**, and executes screenshot/mouse/keyboard actions against a Windows host
via a REST sidecar (`computer-use-windows/windows_server.py`, this repo).

The quality of that beat lives or dies on the **prompts**. Tuning them by editing
Mendix and re-running the whole stack is slow and not repeatable. We want a fast,
scriptable way to iterate on the system/user prompts and **measure** whether the agent
reliably and safely completes each form — then paste the winning prompts back into
Mendix for the live demo.

### The prompts already have an injection point

The Mendix caller microflow (model unit `0230cfc1-75fa-4a50-9ea0-8074cae03e2b`) already
supports per-run overrides:

- System: `if EnquiryManagementMemory.TestSystemPrompt not empty then TestSystemPrompt else <default>`
- User: `if EnquiryManagementMemory.TestUserPrompt not empty then TestUserPrompt else <default>`

Current default **system** prompt:

> "You are an automation agent operating the Complaint Resolution System v2.3 desktop
> application on Windows. The window may be minimised - bring it to focus first. The form
> has these fields: Case ID (pre-filled), Customer (pre-filled), Product (pre-filled),
> Resolution (text area - required), Status (dropdown - required, do not leave as Pending),
> and Dispatch Ref (text box - required). Fill all required fields then click Submit."

Current default **user** prompt:

> "Fill in the Complaint Resolution System: Resolution: {RecommendedAction}; Status:
> Replacement Approved; Dispatch Ref: DISP-{UUID}. Click Submit when complete."

The lab's optimised prompts will be pasted into `TestSystemPrompt` / `TestUserPrompt`
(and ultimately promoted to the microflow defaults) for the demo.

## 2. Goals & non-goals

### Goals
- Iterate on system + user prompts in Python **fast and repeatably**, with measured outcomes.
- **Faithfully mirror** the Mendix Bedrock request so a prompt that wins in the lab wins in the demo.
- Support **two run modes** that match the demo:
  - `single_prompt` — desktop app, one autonomous instruction.
  - `conversational` — web portal, a **sequence** of presenter-issued prompts (live, sequential).
- Score on **correctness**, **robustness across scenarios/repeats/phrasings**, and **safety**.
- Compare **multiple models** (Opus 4.7 vs Sonnet 4.5) as a matrix axis.
- **Export** winning prompts as paste-ready strings for Mendix.

### Non-goals
- No changes to the Mendix model in this project (prompts are pasted in manually / via MCP later).
- Not a CI gate. It is a developer-run optimisation tool ("prompt lab").
- No LLM-as-judge scoring — ground truth is exact, so scoring is a deterministic comparison.
- We do **not** reimplement the executor; we reuse the existing `/computer_tool` REST service.

## 3. Architecture

The lab plays **the exact role Mendix plays**: it runs the Bedrock agent loop itself and
sends every tool action over the existing REST contract to the Windows executor. The
screen, executor, and target apps are untouched.

```
 prompt_lab/  (this repo, runs on dev laptop)
   runner ──► bedrock_loop ──(boto3 converse)──► AWS Bedrock (Claude, eu-west-1)
                  │  ▲
                  │  └── tool_result (text + screenshot)
                  ▼
            executor_client ──(HTTP POST /computer_tool)──► windows_server.py  (host:8081)
                                                                  │ pyautogui
                                                                  ▼
                                                            Windows desktop
                                                              ├── Warranty Case Manager (tkinter)
                                                              └── Browser → Returns Dispatch Portal (Flask :5050)
   runner ──(HTTP /control/setup, /control/records)──────────► windows_server.py  (host:8081)
   scoring ◄── records JSON
   mendix_export ──► paste-ready TestSystemPrompt / TestUserPrompt
```

**Process location.** The lab runs on the developer laptop. Tool actions go over REST to
`host:8081/computer_tool` exactly as Mendix does. Because setup/reset/scoring must read
the target apps' state remotely, we add small **control endpoints** to `windows_server.py`
(see §6.2).

## 4. The replicated agent loop

Per run, `bedrock_loop` reproduces what the Mendix microflow does:

1. Build a Bedrock `converse` request:
   - `system` = the variant's system prompt.
   - first `user` message = the variant's user prompt (templated with the scenario's case data).
   - tool config = the `computer` tool spec for the chosen model (correct version + beta flag, display dims).
2. Claude returns a `tool_use` for `computer` (`screenshot` / `left_click` / `type` / `key` / `scroll` / …).
3. `executor_client` maps it to the `/computer_tool` JSON, POSTs it, receives `{output, base64image}`.
4. Return a `tool_result` (text + image block) to Claude; loop.
5. Stop on `end_turn`, on the **step cap** (safety), or — in `conversational` mode — when the
   agent yields and the driver supplies the next user prompt.
6. Capture a transcript: messages, tool calls, per-turn token usage, stop reason, wall-clock.

### Mode: `single_prompt` (desktop)
One system + one user prompt; the loop runs autonomously to `end_turn` or the step cap.
This is the bounded, workflow-triggered desktop fill.

### Mode: `conversational` (web)
A **sequence** of user prompts (mirrors the presenter typing prompts live, one after
another). After the agent yields each turn, the **driver** supplies the next user prompt
on the same message history. Two interchangeable drivers:
- **scripted** — the scenario lists the exact ordered user prompts (this *is* the demo
  script; fully deterministic).
- **persona** — a second Claude call plays the presenter: given the goal + case data + the
  latest screenshot/agent message, it emits the next prompt in its own words, or signals
  "done". Used to stress-test prompt robustness against phrasing variation. Seeded for
  reproducibility.

## 5. Components (each isolated, with a clear interface)

| Module | Responsibility | Key interface | Depends on |
|---|---|---|---|
| `bedrock_loop.py` | Run one agent loop turn-sequence | `run(model, system, messages, tools, executor, step_cap, driver?) -> Transcript` | boto3, `executor_client` |
| `executor_client.py` | REST client for `/computer_tool` | `act(action_input) -> {output, image_b64, error}` | stdlib http |
| `models.py` | Per-model id + tool version + beta flag + display dims + price | `spec_for(model_key) -> ModelSpec` | — |
| `drivers/scripted.py` | Feed next scripted prompt when agent yields | `next(state) -> str \| DONE` | — |
| `drivers/persona.py` | LLM presenter; goal-driven next prompt | `next(state) -> str \| DONE` | boto3 |
| `scenarios/` (data) | target app + case data + expected record + mode + (script\|goal) | YAML | — |
| `prompts/` (data) | system + user prompt variants | Markdown/YAML | — |
| `scoring.py` | Compare result record to expected; safety checks | `score(scenario, records, transcript) -> Result` | — |
| `runner.py` | Matrix run + setup/reset + report | CLI | all of the above |
| `report.py` | Render Markdown + JSON comparison | `write(results) -> paths` | — |
| `mendix_export.py` | Emit paste-ready prompt strings | `export(variant) -> text` | — |

### Design notes
- `bedrock_loop` is the **only** module that talks to Bedrock, and `executor_client` the
  only one that talks to the executor. Drivers and scoring never touch the wire formats.
- The two drivers share one interface so `bedrock_loop` is mode-agnostic; `single_prompt`
  is just "no driver / zero extra turns".

## 6. Contracts

### 6.1 Executor contract (existing — do not change)
`POST /computer_tool` on port `8081` (override `COMPUTER_USE_PORT`).

Request JSON:
```json
{ "action": "screenshot|mouse_move|left_click|right_click|double_click|type|key|scroll",
  "coordinate": [x, y], "text": "…", "key": "ctrl+a",
  "scroll_direction": "up|down|left|right", "scroll_amount": 3 }
```
Response: `200 {"output": "…", "base64image": "<PNG b64>"}` — a fresh screenshot is returned
**after every action** — or `400 {"error_message": "…"}`. Keys are X11 keysyms (mapped to
pyautogui server-side); single-threaded, sequential.

### 6.2 Control endpoints (new — add to `windows_server.py`)
Logic lives in a new isolated module (e.g. `scenario_control.py`) that `windows_server.py`
routes to, keeping the action code untouched.

- `POST /control/setup` — body `{ "app": "warranty"|"returns", "case": {…prefill…} }`.
  Kills any running instance of the target, clears its records file, launches it fresh,
  brings it to focus (web: ensure Flask up + browser tab at `localhost:5050`, focused).
  Returns `{ "ready": true, "baseline_count": N }`.
- `GET /control/records?app=warranty|returns` — returns `{ "records": [...], "count": N }`
  from the app's JSON file, for scoring.
- `POST /control/teardown` (optional, best-effort) — close the app/tab.
- `GET /control/health` — `{ "ok": true }`.

## 7. Data formats

### 7.1 Scenario (`scenarios/*.yaml`)
```yaml
id: warranty-wheel-replacement
mode: single_prompt          # or: conversational
target: warranty             # warranty | returns
case:                        # injected into prompt templates + used by /control/setup
  case_id: EQ-2026-0042
  customer: "Robertson, J."                       # Berlin fleet operator, ~200 vehicles
  product: "Evora Alloy Wheel AW-200"             # rear alloy wheel (AW-200-REAR)
  recommended_action: >
    Approve free-of-charge replacement of the affected rear alloy wheels and
    raise a safety recall (34 cracked, 6 road failures, 2 injuries).
  uuid: "A1B2C3"
expected_record:             # ground truth for scoring (keys mirror the app's JSON schema)
  Resolution: { contains: "replacement" }
  Status: "Replacement Approved"
  DispatchRef: "DISP-A1B2C3"
# conversational only:
script:                      # scripted driver — the exact demo prompt sequence
  - "Open the returns portal and start a new dispatch record for case EQ-2026-0042."
  - "Set dispatch type to Wheel Replacement and courier to DHL."
  - "Add the shipping address and a brief note, then create the dispatch record."
goal: >                      # persona driver — same intent, free phrasing
  Create a Wheel Replacement dispatch record for case EQ-2026-0042 via DHL,
  with a shipping address and a short note, and submit it.
max_user_prompts: 4          # conversational efficiency cap
```

> **Ground truth note.** The demo scenario is the **Evora reinforced alloy-wheel failure**
> complaint (source: `boat-2026/outputs/demo-complaint-email-wheels.md`): a Berlin fleet
> operator (Joe Robertson, ~200 vehicles) reporting 34 cracked rear wheels, 6 road
> failures, 2 injuries. The computer-use agent records the warranty resolution in the
> desktop app and creates the replacement dispatch in the web portal. The live apps
> already prefill this narrative — `warranty_case_manager.py` (Customer `Robertson, J.`,
> Product `Evora Alloy Wheel AW-200`, Case `EQ-2026-0042`) and `returns_portal/app.py`
> (`product_code AW-200-REAR`, dispatch type `Wheel Replacement`) — so scenario data and
> app data agree. `expected_record` keys mirror the actual app JSON; the implementer reads
> exact field names from the two app files when authoring scenarios.

### 7.2 Prompt variant (`prompts/*.md`)
A file per variant with `system:` and `user:` blocks (user supports `{placeholders}` filled
from `scenario.case`). Variant id = filename. Version-controlled and diff-friendly.

### 7.3 Report (`report.py`)
Markdown + JSON. One row per `{variant × scenario × model × repeat}` cell aggregated to:
pass-rate, mean steps, mean tokens (in/out), est. cost, mean latency, and failure reasons.
Highlights the best variant per target.

## 8. Scoring (`scoring.py`)

A run **passes** when all hold:

**Correctness** (record vs `expected_record`)
- Exactly one new record appended since `baseline_count` (submitted once).
- All required fields non-empty.
- `Status` equals expected and is **not** `Pending`.
- `DispatchRef` matches expected (e.g. `DISP-{uuid}`).
- Dropdown fields (dispatch type, courier) equal expected.
- Free-text fields satisfy declared constraints (`contains`, regex).

**Safety**
- Loop finished under the step cap (no runaway).
- No executor `error_message` and no error dialog/validation popup left on screen.
- No destructive control used (e.g. Clear/Delete) — detected via action log.
- `conversational`: completed within `max_user_prompts`.

**Captured (not pass/fail, for comparison):** steps, tool-call count, tokens, est. cost,
latency.

Result: `{ passed: bool, reasons: [...], metrics: {...} }`.

## 9. Models

| Key | Bedrock model id | Tool version | Beta flag |
|---|---|---|---|
| `opus-4-7` | `eu.anthropic.claude-opus-4-7` | `computer_use_20251124` | `computer-use-2025-11-24` |
| `sonnet-4-5` | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` | `computer_use_20250124` | `computer-use-2025-01-24` |

Region `eu-west-1`, account `770071634381`, inference profiles. `models.py` is the single
source for id/version/beta/display-dims/price; `bedrock_loop` selects per run. The shared
executor handles both action sets.

## 10. Directory layout

```
prompt_lab/
  __init__.py
  models.py
  bedrock_loop.py
  executor_client.py
  scoring.py
  runner.py
  report.py
  mendix_export.py
  drivers/
    __init__.py
    scripted.py
    persona.py
  prompts/
    warranty_v1.md
    returns_v1.md
  scenarios/
    warranty-wheel-replacement.yaml
    returns-wheel-replacement.yaml
  reports/            # generated
  README.md
computer-use-windows/
  windows_server.py   # + /control/* routing
  scenario_control.py # new: setup/reset/read-records logic
```

## 11. Prerequisites & infrastructure

- **AWS creds on the laptop** for Bedrock (SSO default profile, `eu-west-1`, or the
  `bedrock` IAM user). Bedrock calls originate from the laptop.
- **Network reachability** laptop → host: `8081` (`/computer_tool` + `/control/*`). Mendix
  already calls `8081` on the host, so the security group likely allows it — **verify** for
  the laptop's IP; widen the SG or tunnel via SSH if not.
- **Host running** the demo environment (`start_demo_env.bat`): `windows_server.py`, the two
  target apps, and a browser. The EC2 demo host (`i-03b6f82830b1011c2`) is one option; note
  its public IP is ephemeral across stop/start unless an Elastic IP is attached.
- **Python deps** for the lab: `boto3`, `pyyaml`, `requests` (or stdlib http).

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Lab fidelity drifts from Mendix (different tool version/flag/dims) → lab wins don't transfer | `models.py` pins version+beta+dims per model; keep request shape identical to the microflow; optionally validate the final winner once through real Mendix. |
| DPI scaling / coordinate drift on the host | Host server already sets per-monitor DPI awareness + `pyautogui.PAUSE`; run against the actual demo hardware. |
| Browser focus / wrong tab in `conversational` runs | `/control/setup` pins and focuses the portal tab; minimise other windows. |
| Persona driver flakiness inflates failures | Seed it; treat scripted as the regression signal and persona as stress-only. |
| Bedrock cost during big matrices | Default to small repeat counts; iterate on `sonnet-4-5` then confirm winner on `opus-4-7`. |
| Control endpoints widen the host's surface | Keep them minimal, demo-only; host SG is IP-restricted. |

## 13. Open items & out of scope

### Open items (resolve before/early in implementation)
- **Confirm the JSON record schema** the apps actually write (exact keys/case) by reading
  `warranty_case_manager.py` and `returns_portal/app.py`; `expected_record` keys must match
  them verbatim. (Narrative is settled: Evora alloy-wheel complaint, and the apps already
  prefill it.)

### Out of scope (deferred)
- Automated push of prompts into Mendix (manual paste for now; MCP push later).
- A third target / real Mendix UI as a test surface.
- LLM-judge or fuzzy success scoring.
- CI integration.

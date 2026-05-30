# BOAT 2026 Computer-Use Demo — Flow

End-to-end reference for the computer-use beat of the BOAT 2026 demo (Storyboard Step 13–14):
after a manager approves a warranty resolution, a bounded computer-use agent writes the
outcome into two legacy systems that have **no API** — proving "live UI action in a
Windows desktop **and** a web app."

## Narrative

We follow **Evora** (EV manufacturer). A B2B/fleet customer (Berlin fleet operator,
"Robertson, J.") reports **cracked rear alloy wheels** (`demo-complaint-email-wheels.md`).
The enquiry is triaged, escalated, and a manager approves a **warranty replacement**. That
approval triggers the computer-use agent to:

1. **Desktop:** record the resolution in the legacy **Complaint Resolution System v2.3**
   (Warranty Case Manager).
2. **Web:** create the replacement shipment in the legacy **Returns Dispatch Portal**.

The result flows back into the Mendix workflow.

## Architecture

```
Mendix app (workflow + Amazon Bedrock computer-use agent)
   │  builds the request: system prompt + user prompt + the `computer` tool
   │  (AmazonBedrockConnector + GenAICommons.ChatCompletions_WithoutHistory)
   │
   │  per tool action:  POST http://<HOST>:8081/computer_tool   { action, coordinate, text, key, ... }
   ▼
windows_server.py  (Windows executor, pyautogui)  ── runs WINDOWLESS via pythonw, logs to C:\cu_server.log
   │  executes the action on the real 1024×768 desktop, returns { output, base64image }
   ▼
Windows desktop (EC2 host, AutoLogon, started by start_demo_env.bat)
   ├── Warranty Case Manager   (tkinter "Complaint Resolution System v2.3")  ← desktop beat
   └── Microsoft Edge → Returns Dispatch Portal (Flask, localhost:5050)        ← web beat
```

The agent loop (screenshot → Claude → action → screenshot …) lives in Mendix/Bedrock. This
repo is the **executor** it drives. `prompt_lab/` replicates that loop in Python to optimise
the prompts (see below).

## The two beats

### 1. Warranty desktop (single autonomous prompt)
The agent focuses the (minimised) window, fills **Resolution / Status / Dispatch Ref**, and
clicks **Submit**. One instruction, runs to completion.

- **Optimised system prompt:** `warranty_v3` — **18/18 (100%)** on Claude Sonnet 4.5, ~17 steps, ~$0.55/run.
- Stored as Mendix constant **`AgentCore.WarrantyComputerUseSystemPrompt`**.
- The user prompt supplies the values: `Resolution = {RecommendedAction}; Status = Replacement Approved; Dispatch Ref = DISP-{UUID}`.

### 2. Returns web (directive prompt; sequence it live)
The agent ensures the blank form is showing (navigates to `localhost:5050` if not), fills
**Dispatch Type / Shipping Address / Courier / Notes**, and clicks **Create Dispatch Record**.

- **Optimised system prompt:** `returns_s2` — **10/10 (100%)** on Sonnet 4.5, ~11 steps, ~$0.28/run.
- Stored as Mendix constant **`AgentCore.ReturnsComputerUseSystemPrompt`**.
- For the live demo you can split the single user instruction into sequential prompts
  (e.g. "set Dispatch Type + Courier", then "add the address + note, then create the record")
  without changing the system prompt. Keep each prompt **directive** ("do it now", not "tell me when ready").

**Model:** use **Sonnet 4.5**. On the desktop beat it beat Opus 4.7 (6/8) and is ~10× cheaper;
returns ran entirely on Sonnet. Full data: [`prompt_lab/OPTIMIZATION_RESULTS.md`](../prompt_lab/OPTIMIZATION_RESULTS.md).

## Known-good starting state (reset)

The prompts assume the apps are running and in a clean state. They tolerate the common
variations (minimised window, dirty fields, wrong browser page — returns self-recovers 4/4),
but the **warranty app disables Submit after a submission and no prompt can recover from
that**. So the environment is reset to a known-good state:

- **Warranty auto-reset:** the desktop app clears its form, re-enables Submit and re-minimises
  ~6s after each submit (and whenever the `_reset.txt` token changes). Self-healing — no caller action.
- **Explicit reset endpoint:** `GET http://<HOST>:8081/reset?app=warranty` (or `?app=returns`)
  clears the records file + bumps the reset token, and for returns opens a fresh form tab.
  Returns `{"ready": true, "app": "..."}`.

### Triggering the reset from Mendix
Optional (warranty already auto-resets). To guarantee a clean state, add a **Call REST**
(GET) as the first step of the microflow that launches each beat:

```
GET  'http://' + $LocalhostIPAddress + ':8081/reset?app=warranty'   (or ?app=returns)
```

`$LocalhostIPAddress` is the existing `ComputerUse_AmazonBedrock.LocalhostIPAddress` constant
(the same host the module already calls for `/computer_tool`).

## Running the demo

1. **Host:** the EC2 Windows host (CloudFormation stack `boat-computer-use`, eu-west-1) boots
   with AutoLogon and runs `start_demo_env.bat`, which launches the Returns Portal (Flask :5050),
   the Warranty Case Manager (minimised), opens Edge at `localhost:5050`, and starts
   `windows_server.py` (port 8081, windowless). Deploy/stack scripts are in `computer-use-windows/aws-deploy/`.
2. **Screen:** the host desktop is **1024×768**. The Bedrock `computer` tool's `display_width/height`
   **must match** this, or clicks land in the wrong place. (RDP at ~1024×768 for manual viewing.)
3. **Network:** Mendix → host on `8081`. Security group allows the presenter's IP on 3389 (RDP),
   8081 (executor), 5050 (portal), 6080 (noVNC viewer).
4. **Mendix:** point `ComputerUse_AmazonBedrock.LocalhostIPAddress` at the host's public IP; set
   the system prompts from the `AgentCore.*ComputerUseSystemPrompt` constants; trigger the beat
   from the approved-warranty path.

## Re-optimising the prompts

`prompt_lab/` runs the Bedrock computer-use loop in Python against the *same* `/computer_tool`
executor, scores each run against the apps' submitted records, and compares prompt variants ×
models × repeats. See [`prompt_lab/README.md`](../prompt_lab/README.md). Winners are exported
as paste-ready `TestSystemPrompt`/`TestUserPrompt` and (now) stored as the `AgentCore` constants.

## Gotchas (see AGENTS.md for the full list)

- Display dims must equal the host resolution (1024×768).
- Run the executor **windowless** (pythonw) — a console window can be killed by a stray agent keystroke.
- Reset apps via files (`_reset.txt` token + records clear), never by killing/spawning processes from the server.
- SSO/Bedrock tokens expire after a few hours — long unattended runs need re-auth.

# Computer-Use Agent — Use Case & Prompts

> A bounded **computer-use agent** that, once a manager approves a warranty resolution, writes
> the outcome into two **legacy systems that have no API** — operating them by screenshot +
> mouse/keyboard. It is the "execute a live UI action in a Windows desktop **and** a web
> application" proof (Gartner **UI-Based Automation / Computer Use**), embedded as a last-mile
> step inside the Evora warranty-resolution flow (Storyboard Step 13–14).

*Canonical copy lives in the BOAT 2026 demo knowledge base (`boat-2026/outputs/computer-use-agent-usecase-and-prompts.md`); this is the repo copy. See also [`docs/demo-flow.md`](demo-flow.md) and [`prompt_lab/OPTIMIZATION_RESULTS.md`](../prompt_lab/OPTIMIZATION_RESULTS.md).*

---

## 1. Use case

| | |
|---|---|
| **Trigger** | The approved-warranty path in the Mendix workflow. A fleet customer ("Robertson, J.", Berlin) reported cracked rear alloy wheels (demo complaint email — wheels); triage → escalation → **manager approves a warranty replacement**. That approval fires the agent. |
| **Goal** | Record the resolution and raise the replacement shipment in two legacy back-office systems that **cannot be integrated via API/connector**, then hand control back to the workflow. |
| **Why computer use** | These systems have no integration surface. The agent proves UI automation as a governed, bounded last-mile action — not a standalone RPA bot. |
| **Surfaces (two beats)** | **Desktop:** *Complaint Resolution System v2.3* (Warranty Case Manager). **Web:** *Returns Dispatch Portal* (browser). |
| **Capability shown** | Gartner UI-Based Automation / Computer Use — live UI action across a Windows desktop and a web app, integrated into a Mendix workflow. |

## 2. How it runs

The agent loop (screenshot → Claude decides → action → screenshot …) runs in **Mendix + Amazon
Bedrock** (`AmazonBedrockConnector` + `GenAICommons.ChatCompletions_WithoutHistory`, with the
`computer` tool). Each action is sent as `POST /computer_tool` to a small Windows executor
(`computer-use-windows/windows_server.py`) on the demo host, which performs it with pyautogui on
the real desktop and returns a fresh screenshot. The two target apps run on that desktop. Detail:
[`docs/demo-flow.md`](demo-flow.md) and `computer-use-windows/` (+ the receiving-system spec in the demo knowledge base).

- **Model:** Claude **Sonnet 4.5** (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`). Chosen over
  Opus 4.7 — more reliable on this task and ~10× cheaper.
- **Display:** the host desktop is **1024×768**; the computer-use tool's display dimensions must
  match, or clicks miss.
- **Case inputs** (from the workflow): `RecommendedAction` (resolution text), `UUID`
  (→ Dispatch Ref `DISP-{UUID}`), `CaseRef` (`EQ-2026-0042`); customer/product are pre-filled in the apps.

---

## 3. Beat 1 — Warranty desktop (single autonomous prompt)

The agent focuses the (minimised) window, fills **Resolution / Status / Dispatch Ref**, and clicks
**Submit** — one instruction, run to completion.

- **Validated:** **18/18 (100%)** on Sonnet 4.5, ~17 steps, ~$0.55/run.
- **Stored as:** Mendix constant `AgentCore.WarrantyComputerUseSystemPrompt`.

**System prompt**
```
You operate the "Complaint Resolution System v2.3" Windows desktop application via screenshots and mouse/keyboard. The window often starts minimised — your FIRST actions must be: take a screenshot, then click the app's button on the taskbar to bring it to the foreground. Confirm the window is visible with another screenshot before typing anything.
When entering text: click the target field, press Ctrl+A then Delete to clear it, then type the new value. For the Status dropdown, click to open it and select the requested option by clicking it. Never type into the read-only Customer or Product fields. Before submitting, take a screenshot and confirm Resolution, Status and Dispatch Ref are all set and Status is not "Pending". Then click Submit once.
```

**User prompt** (template — values from the case)
```
Fill the form and submit:
Resolution = {RecommendedAction}
Status = Replacement Approved
Dispatch Ref = DISP-{UUID}
```

---

## 4. Beat 2 — Returns web (directive prompt; sequence it live)

The agent ensures the blank form is showing (navigates to `localhost:5050` if not), fills
**Dispatch Type / Shipping Address / Courier / Notes**, and clicks **Create Dispatch Record**.

- **Validated:** **10/10 (100%)** on Sonnet 4.5, ~11 steps, ~$0.28/run.
- **Stored as:** Mendix constant `AgentCore.ReturnsComputerUseSystemPrompt`.

**System prompt**
```
You are operating a legacy web form (the "Returns Dispatch Portal") in a browser at localhost:5050 by screenshot and mouse/keyboard. Be decisive and act - click and type, do not narrate.
Step 0: screenshot. If the empty form is not shown (e.g. a confirmation page is up), navigate to http://localhost:5050 via the address bar first.
Then complete the form the user describes:
- Dropdowns (Dispatch Type, Courier): click to open, then click the exact option.
- Text fields (Shipping Address lines, Notes): click into the field and type.
- Leave the pre-filled Case Reference / Customer / Product Code.
Finish by clicking "Create Dispatch Record"; screenshot to confirm the record was created.
```

**User prompt** (single instruction)
```
In the Returns Dispatch Portal, raise a dispatch for case {CaseRef}. Set Dispatch Type = "Wheel Replacement", Courier = "DHL", Shipping Address = "Depot 4, Hansastrasse 22, Berlin", Notes = "Replacement rear alloy wheels under warranty", then create the record.
```

**Live-demo pacing:** to drive this conversationally on stage, split the single instruction into
sequential prompts **without changing the system prompt**, e.g. (1) "Set Dispatch Type to Wheel
Replacement and Courier to DHL"; (2) "Add the shipping address and a note, then create the dispatch
record." Keep each prompt directive ("do it now", not "tell me when ready") — passive, multi-turn
phrasing was markedly less reliable in testing.

---

## 5. Preconditions & reset (known-good state)

The prompts assume the apps are running and on a clean starting state. They tolerate common
variation (minimised window, dirty fields, wrong browser page — returns self-recovers 4/4), **but
the warranty desktop app disables Submit after a submission and no prompt can recover from that.**
So the environment is reset to a known-good state:

- **Warranty auto-reset:** the desktop app clears its form, re-enables Submit and re-minimises
  ~6 s after each submit (and whenever a `_reset.txt` token changes). Self-healing — no caller action.
- **Explicit reset:** `GET http://<HOST>:8081/reset?app=warranty` (or `?app=returns`) forces a clean
  state (clears the records file + bumps the token; opens a fresh form tab for returns).
- **Trigger from Mendix (optional):** add a Call REST (GET) to
  `'http://' + $LocalhostIPAddress + ':8081/reset?app=warranty'` as the first step of the microflow
  that launches each beat. `$LocalhostIPAddress` is the existing `ComputerUse_AmazonBedrock.LocalhostIPAddress`.

Robustness measured: **warranty 1/4** with no reset between runs (needs the reset); **returns 4/4**
(self-recovers by navigating back to a fresh form).

---

## 6. Where the prompts live & how to re-optimise

- **Production:** Mendix constants `AgentCore.WarrantyComputerUseSystemPrompt` and
  `AgentCore.ReturnsComputerUseSystemPrompt` (point the computer-use microflow's system prompt at these).
- **Source + evidence:** `prompt_lab/prompts/warranty_v3.md`, `prompt_lab/prompts/returns_s2.md`;
  full results in [`prompt_lab/OPTIMIZATION_RESULTS.md`](../prompt_lab/OPTIMIZATION_RESULTS.md).
- **Re-optimise:** `prompt_lab/` runs the same Bedrock computer-use loop in Python against the same
  `/computer_tool` executor, scores each run against the apps' submitted records, and compares
  prompt variants × models × repeats. That is how `warranty_v3` and `returns_s2` were selected.

---

## 7. Reliability summary (Sonnet 4.5)

| Beat | Prompt | Reliability | Steps | Cost/run |
|---|---|---|---|---|
| Warranty desktop | `warranty_v3` | 18/18 (100%) | ~17 | ~$0.55 |
| Returns web | `returns_s2` | 10/10 (100%) | ~11 | ~$0.28 |

Opus 4.7 was worse on the desktop beat (6/8) and ~7–13× the cost — **use Sonnet 4.5**.

> Note: these apps run the **Evora alloy-wheel** narrative (case `EQ-2026-0042`, "Robertson, J.",
> "Evora Alloy Wheel AW-200", dispatch type "Wheel Replacement"). The older receiving-system spec
> still shows the earlier sensor/Müller placeholder data — this document reflects the deployed apps.

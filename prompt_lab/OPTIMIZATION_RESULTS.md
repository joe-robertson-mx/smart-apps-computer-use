# Computer-Use Prompt Optimization — Results

**Date:** 2026-05-30
**Target:** BOAT 2026 computer-use beat (Storyboard 13) — Evora alloy-wheel warranty resolution.
**Method:** The `prompt_lab` harness ran the real Bedrock computer-use loop against the live
EC2 demo host (`3.249.25.226`), driving the actual Windows apps over the existing
`/computer_tool` REST contract — exactly how Mendix drives them. Screen: 1024×768.
Each run is scored on the real app's submitted record (correct fields + safe behaviour).

---

## TL;DR

- **Warranty desktop beat is solved.** Optimised prompt = **`warranty_v3`** on **Claude Sonnet 4.5**:
  **18/18 (100%)** across all rounds, every run ~16–17 steps, ~**$0.55/run**. Clears the 95% bar.
- **Use Sonnet 4.5, not Opus 4.7, for this beat.** Opus scored **6/8** (two runaways) at **7–13× the cost**
  ($4–9.6/run). Counter-intuitive but consistent: Opus explored more and hit the step cap.
- **Returns web beat is also solved:** `returns_s2` (directive single-prompt) on Sonnet 4.5 =
  **10/10 (100%)**, ~11 steps, ~$0.28/run. Paste-ready prompts for both beats below.

---

## The winning warranty prompt — paste into Mendix

Set these two constants/attributes (`EnquiryManagementMemory.TestSystemPrompt` /
`TestUserPrompt`); they override the microflow defaults.

### TestSystemPrompt (verbatim — this is the part that drove reliability)

```
You operate the "Complaint Resolution System v2.3" Windows desktop application via screenshots and mouse/keyboard. The window often starts minimised - your FIRST actions must be: take a screenshot, then click the app's button on the taskbar to bring it to the foreground. Confirm the window is visible with another screenshot before typing anything.
When entering text: click the target field, press Ctrl+A then Delete to clear it, then type the new value. For the Status dropdown, click to open it and select the requested option by clicking it. Never type into the read-only Customer or Product fields. Before submitting, take a screenshot and confirm Resolution, Status and Dispatch Ref are all set and Status is not "Pending". Then click Submit once.
```

### TestUserPrompt (template — keep the Mendix expressions)

```
Fill the form and submit:
Resolution = {RecommendedAction}
Status = Replacement Approved
Dispatch Ref = DISP-{UUID}
```

In the Mendix microflow expression, `{RecommendedAction}` → `$EnquiryManagementMemory/RecommendedAction`
and `{UUID}` → `$EnquiryManagementMemory/UUID` (same as the existing default user prompt).

---

## Why `warranty_v3` won

It is explicit about the three things the agent otherwise gets wrong on a 1024×768 screen:
1. **Find + focus the minimised window first** (screenshot → click taskbar → confirm) before typing.
2. **Clear each field** with `Ctrl+A` then `Delete` before typing (prevents appending to prefilled text).
3. **Dropdown handling** (click to open, click the exact option) + **verify before a single Submit**.

The result is a near-deterministic ~17-step path — every confirmed run took 16–17 steps with
near-identical cost, which is the signature of a prompt the model can follow the same way every time.
Terser variants (`warranty_v5`, 0/3) gave too little guidance and ran away; `warranty_v2` (lighter
stepwise) degraded to 5/10 under more samples.

---

## Full warranty results (Sonnet 4.5)

| Round | v1 | v2 | **v3** | v4 | v5 | v6 |
|---|---|---|---|---|---|---|
| Screening (×3) | 3/3 | 3/3 | **3/3** | 2/3 | 0/3 | 2/3 |
| Confirmation (×7) | 5/7 | 2/7 | **7/7** | — | — | — |
| Final (×8) | — | — | **8/8** | — | — | — |
| **Total** | 8/10 | 5/10 | **18/18** | 2/3 | 0/3 | 2/3 |

Winner **v3**: 18/18 (100%), 16–20 steps, ~$0.55/run.

## Model comparison (warranty_v3, ×8 each)

| Model | Pass | Steps | Cost/run |
|---|---|---|---|
| **Sonnet 4.5** | **8/8** | 16–17 | **~$0.55** |
| Opus 4.7 | 6/8 | 19–28 (2 runaways @30) | ~$4–9.6 |

**Recommendation: Sonnet 4.5** — more reliable here and ~10× cheaper.

---

## Returns / web beat

**Solved.** Optimised prompt = **`returns_s2`** (single-prompt, directive) on **Sonnet 4.5**:
**10/10 (100%)**, steady **11 steps**, ~**$0.28/run**. All three directive variants (`returns_s1/s2/s3`)
scored 10/10; `s2` is the tightest.

### What it took
The conversational, multi-turn approach was unreliable (1/10, then 0/9). Two root causes, both fixed:
1. **Stale browser between episodes** — after a submit the browser sat on the confirmation page, so
   later episodes never saw a blank form. Fix: `/control/setup` now opens a fresh form tab in the
   **existing** browser (killing + cold-restarting msedge was worse — it showed a restore/first-run page).
2. **Passive prompting** — "one step at a time / wait for instructions" made the agent describe rather
   than act. Fix: a **directive single-prompt** that names every field value and says act, don't narrate.

### The winning returns prompt — paste into Mendix

**TestSystemPrompt**
```
You are operating a legacy web form (the "Returns Dispatch Portal") in a browser at localhost:5050 by screenshot and mouse/keyboard. Be decisive and act - click and type, do not narrate.
Step 0: screenshot. If the empty form is not shown (e.g. a confirmation page is up), navigate to http://localhost:5050 via the address bar first.
Then complete the form the user describes:
- Dropdowns (Dispatch Type, Courier): click to open, then click the exact option.
- Text fields (Shipping Address lines, Notes): click into the field and type.
- Leave the pre-filled Case Reference / Customer / Product Code.
Finish by clicking "Create Dispatch Record"; screenshot to confirm the record was created.
```

**TestUserPrompt** (fill the values from the case)
```
In the Returns Dispatch Portal, raise a dispatch for case {CaseRef}. Set Dispatch Type = "Wheel Replacement", Courier = "DHL", Shipping Address = "<address>", Notes = "<note>", then create the record.
```

### Demo note (conversational pacing)
You wanted the web beat driven by sequential prompts live. The single-prompt above is the *reliable*
form; for the demo you can split the one user instruction into two sequential prompts without changing
the system prompt — e.g. (1) "set Dispatch Type to Wheel Replacement and Courier to DHL", then
(2) "add the shipping address and a note, then create the dispatch record". The multi-turn variant is
inherently less reliable, so keep each prompt directive ("do it now", not "tell me when ready").

### Returns results (Sonnet 4.5)

| Variant | Screening (×3) | Confirmation (×7) | **Total** | Steps |
|---|---|---|---|---|
| **returns_s2** | 3/3 | 7/7 | **10/10** | 11 |
| returns_s1 | 3/3 | 7/7 | 10/10 | 11 |
| returns_s3 | 3/3 | 7/7 | 10/10 | 13–15 |

Earlier conversational variants (`returns_v1`–`v5`): 1/10 best — not recommended.

---

## How to reproduce

Host must be running `start_demo_env.bat` (windowless server on :8081 + the two apps) and reachable
on 8081 from the runner. AWS creds for Bedrock (`eu-west-1`).

```bash
# screen is 1024x768 on the EC2 host — dims MUST match or clicks miss
PROMPT_LAB_W=1024 PROMPT_LAB_H=768 PROMPT_LAB_STEP_CAP=30 PROMPT_LAB_MAX_IMAGES=2 PROMPT_LAB_SETTLE=4 \
python -m prompt_lab.runner --host http://<HOST_IP>:8081 \
  --prompts "prompt_lab/prompts/warranty_v3.md" \
  --scenarios "prompt_lab/scenarios/warranty-wheel-replacement.yaml" \
  --models sonnet-4-5 --repeats 8
```

Reports land in `prompt_lab/reports/`.

---

## What it took to get a stable rig (notes)

Several real issues surfaced and were fixed before clean data was possible:
- **Display dims** must equal the host's actual resolution (1024×768), or the model's coordinates miss.
- **`key` action**: Claude sends key combos in `text`; the executor reads `key`. The client now remaps
  it (mirroring the Mendix mapping) so `Ctrl+A`/`Escape`/arrows work.
- **Image history**: the loop now keeps only the last few screenshots, bounding cost.
- **Scoring**: recovered tool errors (e.g. an unsupported `triple_click` the agent recovers from) are a
  metric, not a failure.
- **Server stability**: app reset is now done by clearing the records file + a `_reset.txt` token the
  desktop app watches (no process management from the server), and the server runs **windowless**
  (`pythonw`, self-logging) so a stray agent keystroke/click can never focus, Ctrl+C, or close it.
  This was the key fix — earlier the agent occasionally killed the server's console mid-run.

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
- Paste-ready Mendix prompt below.
- **Returns/web beat:** see "Returns" section (screening run).

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

## Returns / web beat (conversational)

_Screening in progress — results appended when complete._

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

# AGENTS.md — smart-apps-computer-use

Orientation for AI agents (and humans) working in this repo. Read this first.

## What this repo is

A computer-use **executor** for the BOAT 2026 demo, plus `prompt_lab/` — a harness that
**optimises the system/user prompts** that drive the computer-use agent.

The Mendix app (the *Enquiry Intake-BOAT* app, separate) runs an Amazon Bedrock (Claude)
computer-use loop and sends each screenshot/mouse/keyboard action to a small HTTP executor in
**this** repo via `POST /computer_tool`. The executor drives a real Windows desktop (pyautogui)
where two legacy demo apps run. `prompt_lab/` replicates that loop in Python (same executor) so
prompts can be measured and tuned offline. Full demo write-up: [`docs/demo-flow.md`](docs/demo-flow.md).

## Layout

- `src/my_server.py` — original Linux/Docker executor (Anthropic tools, xdotool).
- `computer-use-windows/` — the Windows demo:
  - `windows_server.py` — Windows executor (pyautogui). Routes `POST /computer_tool`, `GET|POST /control/*`, `GET /reset`. Runs **windowless** via `pythonw`, logs to `C:\cu_server.log`.
  - `scenario_control.py` — host-side reset logic (clears records JSON + bumps `_reset.txt` token; opens a fresh browser tab for returns). **No process management from the server.**
  - `warranty_case_manager.py` — tkinter "Complaint Resolution System v2.3" (desktop target). Self-resets ~6s after submit and on `_reset.txt` change.
  - `returns_portal/` — Flask "Returns Dispatch Portal" on `:5050` (web target).
  - `start_demo_env.bat` / `stop_demo_env.bat` — launch/stop the demo env (used by AutoLogon on the host).
  - `aws-deploy/` — CloudFormation + scripts for the EC2 demo host (stack `boat-computer-use`, eu-west-1, SSM-managed).
- `prompt_lab/` — the prompt-optimisation harness. See `prompt_lab/README.md` and **`prompt_lab/OPTIMIZATION_RESULTS.md`** (the headline results + paste-ready prompts).
- `docs/demo-flow.md` — end-to-end demo flow.
- `docs/superpowers/specs|plans/` — design spec + implementation plan for the prompt lab.

## Running

- **Tests:** `python -m pytest` from the repo root (`pyproject.toml` sets pythonpath to `.` and `computer-use-windows`). ~43 tests, all pure/unit (no host or Bedrock needed).
- **Prompt lab:** `python -m prompt_lab.runner --host http://<HOST>:8081 --prompts "prompt_lab/prompts/<glob>.md" --scenarios "prompt_lab/scenarios/<file>.yaml" --models sonnet-4-5 --repeats N`. Needs AWS creds (Bedrock, eu-west-1) + a reachable executor.
  - Env: `PROMPT_LAB_W`/`PROMPT_LAB_H` **must match the host screen** (1024×768 on the EC2 host); `PROMPT_LAB_STEP_CAP` (default 30), `PROMPT_LAB_MAX_IMAGES` (default 3), `PROMPT_LAB_SETTLE` (post-reset settle seconds).
- **Demo env (on the host):** `computer-use-windows/start_demo_env.bat`.

## Executor REST contract

`POST /computer_tool` → `{ "action": "screenshot|mouse_move|left_click|right_click|double_click|type|key|scroll", "coordinate": [x,y], "text": "...", "key": "ctrl+a", "scroll_direction": "...", "scroll_amount": 3 }`
→ `200 {"output": "...", "base64image": "<png b64>"}` (a fresh screenshot after every action) or `400 {"error_message": "..."}`.
Plus `GET /control/health`, `POST /control/setup`, `GET /control/records?app=warranty|returns`, `GET /reset?app=warranty|returns`.

## Key facts / gotchas (learned the hard way — don't relearn them)

- **Display dims must equal the host's real resolution (1024×768).** The executor does not scale coordinates; a mismatch makes every click miss. Set `PROMPT_LAB_W/H` and the Bedrock tool's `display_width/height` to match.
- **`key` action:** Claude sends key combos in `text` (`{action:"key", text:"ctrl+a"}`); the executor reads `key`. `prompt_lab/executor_client.py` remaps it (mirroring the Mendix mapping). Without this, Ctrl+A / Escape / arrows silently fail.
- **Run the executor windowless (`pythonw`, self-logging).** With a console window, a stray agent keystroke/click (Ctrl+C, or closing the window) kills the server mid-run. This was the single biggest stability fix.
- **Never manage the target apps' processes from the server.** Spawning/killing from the single-threaded executor is fragile (and previously crashed it). Reset by clearing the records JSON + bumping `_reset.txt` (the desktop app watches it) and opening a fresh browser tab.
- **The warranty desktop app disables Submit after a submission** and no prompt can recover from that state (confirmed: 1/4 with no reset, vs returns 4/4 which self-recovers). It auto-resets ~6s post-submit; `GET /reset?app=warranty` forces it.
- **The loop truncates old screenshots** (keep last N) — otherwise input tokens explode (one early run hit ~800K tokens).
- **Scoring** treats recovered tool errors (e.g. an unsupported `triple_click` the agent recovers from) as a metric, not a failure; only correctness + safety (step cap, destructive action, submitted-once) fail a run.
- **Bedrock:** region `eu-west-1`; models `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` and `eu.anthropic.claude-opus-4-7` (different computer-use tool versions/beta flags — see `prompt_lab/models.py`). **SSO tokens expire after a few hours**; long unattended runs will fail mid-way until `aws sso login` is re-run.
- **The EC2 host is SSM-managed.** Deploy file changes + reboot via SSM (no RDP needed). AutoLogon + `start_demo_env.bat` bring the env back on reboot.

## Current best prompts

- Warranty desktop: **`warranty_v3`** → 18/18 (Sonnet 4.5). Mendix constant `AgentCore.WarrantyComputerUseSystemPrompt`.
- Returns web: **`returns_s2`** → 10/10 (Sonnet 4.5). Mendix constant `AgentCore.ReturnsComputerUseSystemPrompt`.
- **Use Sonnet 4.5**, not Opus 4.7 (more reliable here and ~10× cheaper).

## Conventions

- Match the style of surrounding code. Add/keep unit tests (pytest). 
- Commit messages end with the `Co-Authored-By: Claude ...` trailer; branch off `main` for feature work.
- Files matching `_*.py` / `_*.ps1` at the repo root are local operational scratch (SSM deploy/reboot, smoke, robustness probes) and are gitignored — not part of the shipped code.
- Remotes: `fork` = your writeable fork (`joe-robertson-mx/...`); `origin` = upstream `mendixlabs/...` (read-only for us).

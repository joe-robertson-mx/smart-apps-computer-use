# Windows Receiving System — Computer Use Demo (BOAT 2026)

A Windows-native parallel to the Linux/Docker computer-use setup in the root of
this repo. It exposes the **same** `/computer_tool` REST contract as
`src/my_server.py`, but drives the **real Windows desktop** with `pyautogui` —
no Docker, no Linux, no VNC.

It targets two legacy "receiving systems" for the warranty-resolution beat of
the demo (Storyboard Step 13–14):

1. **Warranty Case Manager** — a legacy desktop app (tkinter).
2. **Returns Dispatch Portal** — a legacy intranet web portal (Flask).

## Components

| File | Role | Port |
|------|------|------|
| `windows_server.py` | HTTP server; receives `/computer_tool` from Mendix, runs pyautogui actions | 8081 |
| `warranty_case_manager.py` | Legacy desktop app (Component 2) | — |
| `returns_portal/app.py` | Legacy web portal (Component 3) | 5050 |
| `start_demo_env.bat` | Clean restart + launches everything in order | — |
| `stop_demo_env.bat` | Stops only this demo's python components | — |
| `reset_demo.bat` | Stops components and clears submitted records | — |
| `data/` | Runtime output: `warranty_cases.json`, `dispatch_records.json` | — |

## Setup

Requires Python 3.x on Windows (tested with 3.11). `tkinter` and `Pillow` ship
with most Python installs; `pyautogui` and `Flask` need installing:

```bat
pip install -r requirements.txt
```

Open the firewall for the server port once (PowerShell, as admin):

```powershell
New-NetFirewallRule -DisplayName "Computer Use Server 8081" -Direction Inbound -LocalPort 8081 -Protocol TCP -Action Allow
```

## Run

```bat
start_demo_env.bat
```

This starts the Flask portal, launches the desktop app (minimised to the
taskbar), opens Edge at `http://localhost:5050`, then runs the computer-use
server in the foreground console (close that window to stop).

To run pieces individually:

```bat
python returns_portal\app.py          REM web portal on :5050
pythonw warranty_case_manager.py      REM desktop app, no console
python windows_server.py              REM computer-use server on :8081
```

## Clean restart / reset between demo runs

Every run of `start_demo_env.bat` is already a clean restart: it stops any
previous instances and deletes the submitted records before starting, so the
desktop app, web form, and data files are all back to their starting state.

- `reset_demo.bat` — stop everything and clear records **without** relaunching.
- `stop_demo_env.bat` — just stop the components.

Both target **only** python processes whose command line references this demo's
scripts, so they never touch Mendix, the browser, or other python apps. The
desktop app and web form hold no persistent state beyond the two JSON files, so
clearing those files + relaunching is a full reset.

## Mendix integration

No Mendix code changes are required — the server speaks the same
`/computer_tool` contract on port 8081. If Mendix runs on a different machine
than this server, set the `ComputerUse` module constant `LocalhostIPAddress` to
this machine's IP. If they share the machine, the default `127.0.0.1` works.

## Deviations from the spec

- **IPv4 bind.** `src/my_server.py` binds IPv6 `"::"`, which dual-stacks to IPv4
  on Linux but **not** on Windows. This server binds IPv4 `0.0.0.0` so the
  Mendix default `127.0.0.1` connects.
- **Flask launch.** The spec's `flask --app returns_portal run` does not resolve
  `returns_portal/app.py` (not a package). The `.bat` runs `app.py` directly.
- **Key translation.** The computer-use model emits xdotool keysyms (`Return`,
  `ctrl+a`, `Page_Down`); `windows_server.py` translates them to pyautogui keys.
- **DPI awareness.** The server marks itself per-monitor DPI aware so screenshot
  pixels and click coordinates share one space on scaled displays.

## Notes / risks

- **Port 8081 conflict with Mendix (found during testing).** On this machine the
  Mendix runtime for the "Enquiry Intake-BOAT" app is bound to `127.0.0.1:8081`
  (and `8091`). Two problems result: (1) the computer-use server cannot bind
  8081, and (2) even binding `0.0.0.0:8081` does not help — Windows routes
  `127.0.0.1` connections to the more-specific Mendix listener, so Mendix would
  call *itself*. **Fix before the demo:** move the Mendix app's runtime/admin
  ports off 8081/8091 (the root README suggests 8082/8092) so 8081 is free, **or**
  run this server on another port via `set COMPUTER_USE_PORT=8083` and point the
  REST call in the Mendix `ComputerUseTool` microflow at that port.
- **Screen resolution vs. click accuracy (important for reliability).** This
  server returns the full-resolution screenshot and clicks the exact coordinates
  it receives. The Anthropic/Bedrock model resizes images whose long edge
  exceeds ~1568 px and then returns coordinates in that *resized* space — which
  would no longer match a 1920×1080+ desktop, so clicks drift. **Recommendation:**
  set the demo display to **1280×800** (or 1366×768) so no resize happens and
  coordinates are 1:1. This matches the resolution the Linux computer-use image
  uses. If the demo must run at full HD, the server needs coordinate scaling
  added (not yet implemented).
- **DPI / resolution.** Coordinates are physical pixels. Test on the actual demo
  hardware. The full-screen screenshot is returned at native resolution; a
  high-res display means larger images for the model.
- **Typing.** `pyautogui.PAUSE = 0.05` plus a per-character interval guards
  against dropped characters.
- **Desktop app starts minimised** so the agent's first action is to bring it
  into focus (matches the storyboard). Change `root.iconify()` in
  `warranty_case_manager.py` if you want it visible on launch.
- **`FAILSAFE` is off** so a click near a screen corner does not abort the run.

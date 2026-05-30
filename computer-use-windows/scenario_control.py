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
import time
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


# Isolate child processes from the computer-use server's console so a child's
# exit/kill can never send a CTRL_C/CTRL_BREAK to (and shut down) the server.
if sys.platform == "win32":
    _DETACH = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x8)
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
else:
    _DETACH = 0
    _NO_WINDOW = 0


def _run(cmd):
    """Run a short command (own console), never hang (hard timeout), never raise."""
    try:
        subprocess.run(cmd, capture_output=True, timeout=20, creationflags=_NO_WINDOW)
    except Exception:
        pass


def _spawn(args):
    """Launch a GUI app fully detached from our console; never raise."""
    try:
        subprocess.Popen(args, cwd=HERE, creationflags=_DETACH, close_fds=True)
    except Exception:
        pass


class SubprocessLauncher:
    """Real host launcher. Hang-proof (every subprocess call times out and is wrapped)
    and scoped so a reset never touches the computer-use server itself.

    warranty: kill the desktop window by title, then relaunch it.
    returns:  keep Flask up; close the browser and reopen a fresh form tab.
    """
    WARRANTY_TITLE = "Complaint Resolution System v2.3"

    def _flask_up(self) -> bool:
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:5050/", timeout=3)
            return True
        except Exception:
            return False

    def stop(self, app):
        # No-op: never kill the browser. A cold msedge restart shows a messy
        # restore/first-run page the agent fights with. The returns reset opens a
        # fresh form tab in the existing browser instead (see start()).
        return

    def start(self, app, case):
        if app == "returns":
            if not self._flask_up():
                _spawn(["pythonw", os.path.join(HERE, "returns_portal", "app.py")])
            if sys.platform == "win32":
                # Open the blank form in the EXISTING browser; it becomes the active
                # tab. No cold restart, so no restore/first-run page to fight.
                _run(["cmd", "/c", "start", "", "msedge", "http://localhost:5050"])


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

    def _reset(self, app: str):
        """Programmatic reset to a known-good starting state for ONE computer-use run:
        clear the app's records file + bump the desktop app's reset token (the app
        watches it and clears its form, re-enables Submit, re-minimises), and for the
        web target open a fresh form tab. Call this before each run so the prompt never
        has to recover from a stale state — e.g. the desktop app disables Submit after a
        submission, which no prompt can undo."""
        os.makedirs(self.data_dir, exist_ok=True)
        if app in RECORDS_FILE:
            open(self._records_path(app), "w", encoding="utf-8").write("[]")
        open(os.path.join(self.data_dir, "_reset.txt"), "w", encoding="utf-8").write(str(time.time()))
        if app == "returns":
            self.launcher.stop("returns")
            self.launcher.start("returns", {})
        return 200, {"ready": True, "app": app, "baseline_count": 0}

    def handle(self, path: str, method: str, body: dict | None):
        parsed = urllib.parse.urlparse(path)
        route = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if route == "/control/health":
            return 200, {"ok": True}

        if route == "/control/setup" and method == "POST":
            return self._reset(body["app"])

        # Simple GET alias so the demo / Mendix can reset the environment to a known
        # state before each computer-use run: GET /reset?app=warranty|returns
        if route == "/reset" and method == "GET":
            return self._reset(query.get("app", ["warranty"])[0])

        if route == "/control/records" and method == "GET":
            app = query.get("app", [""])[0]
            records = self._read_records(app)
            return 200, {"records": records, "count": len(records)}

        if route == "/control/teardown" and method == "POST":
            self.launcher.stop(body.get("app", ""))
            return 200, {"ok": True}

        return 404, {"error_message": f"unknown control route: {route}"}

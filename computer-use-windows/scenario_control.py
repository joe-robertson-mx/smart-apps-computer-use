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

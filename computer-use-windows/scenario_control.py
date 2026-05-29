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
    """Real host launcher. App-specific reset so resetting one app never kills another.

    warranty: kill only the warranty_case_manager.py process, then relaunch it.
    returns:  leave Flask running; close the browser and reopen a fresh form tab.
    """
    def _kill_by_cmdline(self, needle: str):
        if sys.platform != "win32":
            return
        ps = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" "
            "| Where-Object { $_.CommandLine -like '*" + needle + "*' } "
            "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)

    def _flask_up(self) -> bool:
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:5050/", timeout=3)
            return True
        except Exception:
            return False

    def _ensure_flask(self):
        if not self._flask_up():
            subprocess.Popen(["pythonw", os.path.join(HERE, "returns_portal", "app.py")], cwd=HERE)

    def stop(self, app):
        if app == "warranty":
            self._kill_by_cmdline("warranty_case_manager.py")
        elif app == "returns" and sys.platform == "win32":
            # Close the browser so we can reopen a clean form; leave Flask running.
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)

    def start(self, app, case):
        if app == "warranty":
            subprocess.Popen(["pythonw", os.path.join(HERE, "warranty_case_manager.py")], cwd=HERE)
        elif app == "returns":
            self._ensure_flask()
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", "msedge", "http://localhost:5050"])


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

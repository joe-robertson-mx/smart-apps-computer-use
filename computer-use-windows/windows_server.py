"""Windows-native computer-use HTTP server (BOAT 2026 demo).

Mirrors the REST contract of the Linux/Docker `src/my_server.py` so the Mendix
ComputerUse module can drive a real Windows desktop with no code changes.

POST /computer_tool with a JSON body:
    {
      "action": "screenshot" | "left_click" | "right_click" | "double_click"
                | "type" | "key" | "scroll" | "mouse_move",
      "coordinate": [x, y],          # for click/move/scroll-at
      "text": "string",              # for type
      "key": "string",              # for key (xdotool-style, e.g. "ctrl+a")
      "scroll_direction": "up" | "down" | "left" | "right",
      "scroll_amount": 3
    }

Success (200): {"output": "...", "base64image": "<png base64>"}
Error   (400): {"error_message": "..."}
"""

import base64
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

import pyautogui

from scenario_control import ControlHandler

_control = ControlHandler()

# --- Windows DPI awareness -------------------------------------------------
# Without this, on a scaled display (>100%) pyautogui clicks and the captured
# screenshot can live in different coordinate spaces, so clicks miss. Making
# the process per-monitor DPI aware puts both in physical pixels.
if sys.platform == "win32":
    try:
        import ctypes

        # 2 == PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Small pause between pyautogui calls; FAILSAFE off so a click near a screen
# corner during the demo does not abort the whole sequence.
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = False

# Contract port is 8081 (matches the Linux server). Override with
# COMPUTER_USE_PORT if 8081 is taken on the demo machine.
PORT = int(os.environ.get("COMPUTER_USE_PORT", "8081"))

# xdotool / X11 keysyms (what the computer-use model emits) -> pyautogui keys.
KEYSYM_MAP = {
    "return": "enter",
    "kp_enter": "enter",
    "enter": "enter",
    "tab": "tab",
    "escape": "esc",
    "esc": "esc",
    "backspace": "backspace",
    "delete": "delete",
    "space": "space",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "page_up": "pageup",
    "page_down": "pagedown",
    "prior": "pageup",
    "next": "pagedown",
    "home": "home",
    "end": "end",
    "insert": "insert",
    "super": "win",
    "super_l": "win",
    "super_r": "win",
    "meta": "win",
    "win": "win",
    "control": "ctrl",
    "control_l": "ctrl",
    "control_r": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "alt_l": "alt",
    "alt_r": "alt",
    "shift": "shift",
    "shift_l": "shift",
    "shift_r": "shift",
    "caps_lock": "capslock",
    "minus": "-",
    "plus": "+",
    "equal": "=",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "apostrophe": "'",
    "grave": "`",
    "bracketleft": "[",
    "bracketright": "]",
}


def _translate_key_token(token: str) -> str:
    t = token.strip().lower()
    if t in KEYSYM_MAP:
        return KEYSYM_MAP[t]
    if t.startswith("f") and t[1:].isdigit():
        return t  # f1..f24
    return t  # single chars / digits map to themselves


def _press_key(key_combo: str):
    """Handle single keys and combos like 'ctrl+a' or 'ctrl+shift+t'."""
    parts = [_translate_key_token(p) for p in key_combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty key")
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)


def _capture_screenshot_b64() -> str:
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _xy(coordinate):
    if not coordinate or len(coordinate) != 2:
        raise ValueError("action requires a 'coordinate' [x, y]")
    return int(coordinate[0]), int(coordinate[1])


def perform_action(data: dict) -> str:
    """Run one tool action. Returns a short output string or raises ValueError."""
    action = data.get("action")
    coordinate = data.get("coordinate")
    text = data.get("text")
    key = data.get("key")
    scroll_direction = data.get("scroll_direction")
    scroll_amount = data.get("scroll_amount", 3)

    if action == "screenshot":
        return "Screenshot taken"

    if action == "mouse_move":
        x, y = _xy(coordinate)
        pyautogui.moveTo(x, y)
        return f"Moved to ({x}, {y})"

    if action == "left_click":
        x, y = _xy(coordinate)
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"

    if action == "right_click":
        x, y = _xy(coordinate)
        pyautogui.click(x, y, button="right")
        return f"Right-clicked at ({x}, {y})"

    if action == "double_click":
        x, y = _xy(coordinate)
        pyautogui.doubleClick(x, y)
        return f"Double-clicked at ({x}, {y})"

    if action == "type":
        if text is None:
            raise ValueError("'type' action requires 'text'")
        pyautogui.write(str(text), interval=0.02)
        return f"Typed {len(str(text))} characters"

    if action == "key":
        if not key:
            raise ValueError("'key' action requires 'key'")
        _press_key(str(key))
        return f"Pressed {key}"

    if action == "scroll":
        if coordinate:
            x, y = _xy(coordinate)
            pyautogui.moveTo(x, y)
        amount = int(scroll_amount) if scroll_amount is not None else 3
        clicks = amount * 100  # pyautogui scroll clicks are small; scale up
        if scroll_direction == "up":
            pyautogui.scroll(clicks)
        elif scroll_direction == "down":
            pyautogui.scroll(-clicks)
        elif scroll_direction == "left":
            pyautogui.hscroll(-clicks)
        elif scroll_direction == "right":
            pyautogui.hscroll(clicks)
        else:
            raise ValueError("'scroll' requires 'scroll_direction'")
        return f"Scrolled {scroll_direction} {amount}"

    raise ValueError(f"Unknown action: {action!r}")


class ComputerToolHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/control/"):
            code, payload = _control.handle(self.path, "GET", None)
            self._send_json(code, payload)
            return
        self.send_error(405, "Method Not Allowed")

    def do_POST(self):
        if self.path.startswith("/control/"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"error_message": f"Bad request: {exc}"})
                return
            code, payload = _control.handle(self.path, "POST", body)
            self._send_json(code, payload)
            return

        if self.path != "/computer_tool":
            self.send_error(404, "Not Found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length) if content_length else b"{}"
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send_json(400, {"error_message": f"Bad request: {exc}"})
            return

        try:
            output = perform_action(data)
            image_b64 = _capture_screenshot_b64()
            self._send_json(200, {"output": output, "base64image": image_b64})
        except Exception as exc:
            self._send_json(400, {"error_message": str(exc)})

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


def run_server():
    # Bind IPv4 0.0.0.0 so the Mendix default LocalhostIPAddress (127.0.0.1)
    # works. The Linux server binds IPv6 "::", which does NOT dual-stack to
    # IPv4 on Windows.
    httpd = HTTPServer(("0.0.0.0", PORT), ComputerToolHandler)
    print(f"Starting Windows computer-use server on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()

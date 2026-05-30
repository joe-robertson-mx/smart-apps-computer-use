"""Complaint Resolution System v2.3 - legacy desktop app stand-in (BOAT 2026 demo).

A deliberately old-school Windows Forms-looking tkinter app. The computer-use
agent brings it to focus, fills the Resolution / Status / Dispatch Ref fields,
and clicks Submit. On a valid submit the record is appended to
data/warranty_cases.json.

Run with `pythonw warranty_case_manager.py` so no console window appears.
"""

import json
import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
CASES_FILE = os.path.join(DATA_DIR, "warranty_cases.json")
RESET_FILE = os.path.join(DATA_DIR, "_reset.txt")
# Milliseconds after a successful submit before the form auto-resets to a fresh,
# submittable state, so repeated runs/demo takes start clean with no external
# action. Override with WARRANTY_AUTORESET_MS.
AUTO_RESET_MS = int(os.environ.get("WARRANTY_AUTORESET_MS", "6000"))

# Pre-filled demo case so the agent never has to search for a record.
CASE_ID = "EQ-2026-0042"
CUSTOMER = "Robertson, J."
PRODUCT = "Evora Alloy Wheel AW-200"
STATUS_OPTIONS = ["Pending", "Under Investigation", "Replacement Approved", "Rejected", "Resolved"]

# Legacy Windows Forms palette.
BG = "#d4d0c8"          # classic 'control' grey
FIELD_BG = "#ffffff"
FONT = ("Courier New", 10)
LABEL_FONT = ("MS Sans Serif", 9)


class WarrantyCaseManager:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.submitted = False

        root.title("Complaint Resolution System v2.3")
        root.configure(bg=BG)
        root.resizable(False, False)

        pad = {"padx": 8, "pady": 4}
        row = 0

        def label(text, r):
            tk.Label(root, text=text, bg=BG, font=LABEL_FONT, anchor="w").grid(
                row=r, column=0, sticky="nw", **pad
            )

        # Case ID (editable)
        label("Case ID:", row)
        self.case_id = tk.Entry(root, width=34, font=FONT, bg=FIELD_BG, relief="sunken", bd=2)
        self.case_id.insert(0, CASE_ID)
        self.case_id.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Customer (read-only)
        label("Customer:", row)
        tk.Label(root, text=CUSTOMER, bg=BG, font=FONT, anchor="w").grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # Product (read-only)
        label("Product:", row)
        tk.Label(root, text=PRODUCT, bg=BG, font=FONT, anchor="w").grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        # Resolution (multi-line)
        label("Resolution:", row)
        self.resolution = tk.Text(root, width=34, height=5, font=FONT, bg=FIELD_BG, relief="sunken", bd=2, wrap="word")
        self.resolution.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Status (dropdown)
        label("Status:", row)
        self.status = ttk.Combobox(root, values=STATUS_OPTIONS, state="readonly", width=31, font=FONT)
        self.status.current(0)
        self.status.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Dispatch Ref
        label("Dispatch Ref:", row)
        self.dispatch_ref = tk.Entry(root, width=34, font=FONT, bg=FIELD_BG, relief="sunken", bd=2)
        self.dispatch_ref.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Buttons
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        self.clear_btn = tk.Button(btn_frame, text="Clear", width=12, font=LABEL_FONT, command=self.on_clear)
        self.clear_btn.pack(side="left", padx=12)
        self.submit_btn = tk.Button(btn_frame, text="Submit", width=12, font=LABEL_FONT, command=self.on_submit)
        self.submit_btn.pack(side="left", padx=12)
        row += 1

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(root, textvariable=self.status_var, bg=BG, font=LABEL_FONT, anchor="w", relief="sunken", bd=1)
        status_bar.grid(row=row, column=0, columnspan=2, sticky="we", padx=2, pady=(6, 2))

        # Watch for an external reset signal: the lab bumps _reset.txt between
        # episodes, and we reset the form to its starting state with no process
        # restart (restarting the app from the server would risk killing it).
        self._last_reset_token = self._reset_token()
        self.root.after(700, self._poll_reset)

    def _reset_token(self):
        try:
            return open(RESET_FILE, encoding="utf-8").read().strip()
        except Exception:
            return ""

    def _poll_reset(self):
        tok = self._reset_token()
        if tok and tok != self._last_reset_token:
            self._last_reset_token = tok
            self._external_reset()
        self.root.after(700, self._poll_reset)

    def _external_reset(self):
        self.resolution.delete("1.0", tk.END)
        self.status.current(0)
        self.dispatch_ref.delete(0, tk.END)
        self.case_id.delete(0, tk.END)
        self.case_id.insert(0, CASE_ID)
        self.submit_btn.config(state="normal")
        self.submitted = False
        self.status_var.set("Ready")
        self.root.iconify()

    def on_clear(self):
        if self.submitted:
            return
        self.resolution.delete("1.0", tk.END)
        self.status.current(0)
        self.dispatch_ref.delete(0, tk.END)
        self.status_var.set("Cleared")

    def on_submit(self):
        if self.submitted:
            return
        resolution = self.resolution.get("1.0", tk.END).strip()
        status = self.status.get()
        dispatch_ref = self.dispatch_ref.get().strip()
        case_id = self.case_id.get().strip()

        if not resolution or status == "Pending" or not dispatch_ref:
            messagebox.showwarning("Validation", "Please complete all required fields.")
            return

        record = {
            "case_id": case_id,
            "customer": CUSTOMER,
            "product": PRODUCT,
            "resolution": resolution,
            "status": status,
            "dispatch_ref": dispatch_ref,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._append_record(record)

        self.status_var.set(f"Case {case_id} submitted — {status}")
        self.submit_btn.config(state="disabled")
        self.submitted = True
        # Auto-reset to a fresh, submittable state a few seconds later so the next run
        # starts clean with no external action. (The lab also resets explicitly via the
        # _reset.txt token / GET /reset; _external_reset is idempotent.)
        self.root.after(AUTO_RESET_MS, self._external_reset)

    def _append_record(self, record: dict):
        os.makedirs(DATA_DIR, exist_ok=True)
        records = []
        if os.path.exists(CASES_FILE):
            try:
                with open(CASES_FILE, "r", encoding="utf-8") as fh:
                    records = json.load(fh)
            except (json.JSONDecodeError, OSError):
                records = []
        records.append(record)
        with open(CASES_FILE, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)


def main():
    root = tk.Tk()
    WarrantyCaseManager(root)
    # Start minimised to the taskbar: the agent's first action is to bring the
    # window into focus, matching the storyboard.
    root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()

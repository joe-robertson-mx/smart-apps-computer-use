"""Returns Dispatch Portal - legacy intranet web app stand-in (BOAT 2026 demo).

A Flask app deliberately styled like a 2005-era internal portal. The
computer-use agent switches to this browser tab, fills the dispatch form, and
clicks "Create Dispatch Record". Submissions are appended to
data/dispatch_records.json and the user lands on a confirmation page.

Run directly:  python returns_portal/app.py   (serves on localhost:5050)
"""

import json
import os
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RECORDS_FILE = os.path.join(DATA_DIR, "dispatch_records.json")

PORT = 5050

DISPATCH_TYPES = ["Warranty Replacement", "Repair Return", "Goodwill Replacement", "Exchange"]
COURIERS = ["DHL", "UPS", "FedEx", "GLS"]

PREFILL = {
    "case_reference": "WC-2026-0042",
    "customer_name": "Müller, Hans",
    "product_code": "ISU-400",
}

app = Flask(__name__)


def _append_record(record: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    records = []
    if os.path.exists(RECORDS_FILE):
        try:
            with open(RECORDS_FILE, "r", encoding="utf-8") as fh:
                records = json.load(fh)
        except (json.JSONDecodeError, OSError):
            records = []
    records.append(record)
    with open(RECORDS_FILE, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)


@app.route("/")
def index():
    return render_template(
        "index.html",
        prefill=PREFILL,
        dispatch_types=DISPATCH_TYPES,
        couriers=COURIERS,
    )


@app.route("/submit", methods=["POST"])
def submit():
    reference = "DSP-" + datetime.now().strftime("%Y%m%d%H%M%S")
    record = {
        "reference": reference,
        "case_reference": request.form.get("case_reference", ""),
        "customer_name": request.form.get("customer_name", ""),
        "product_code": request.form.get("product_code", ""),
        "dispatch_type": request.form.get("dispatch_type", ""),
        "shipping_address_1": request.form.get("shipping_address_1", ""),
        "shipping_address_2": request.form.get("shipping_address_2", ""),
        "courier": request.form.get("courier", ""),
        "notes": request.form.get("notes", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _append_record(record)
    return redirect(url_for("confirmation", reference=reference))


@app.route("/confirmation")
def confirmation():
    reference = request.args.get("reference", "DSP-UNKNOWN")
    return render_template("confirmation.html", reference=reference)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

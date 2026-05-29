"""Render the matrix results to Markdown + JSON."""
import json
import os
from datetime import datetime


def render_markdown(cells: list[dict]) -> str:
    total = len(cells)
    passed = sum(1 for c in cells if c["passed"])
    rate = round(100 * passed / total) if total else 0
    lines = [
        "# Prompt Lab Report",
        "",
        f"Pass rate: **{passed}/{total} ({rate}%)**",
        "",
        "| Variant | Scenario | Model | Pass | Steps | Cost $ | Reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        reasons = "; ".join(c.get("reasons", [])) or "—"
        mark = "✅" if c["passed"] else "❌"
        lines.append(f"| {c['variant']} | {c['scenario']} | {c['model']} | {mark} "
                     f"| {c.get('steps', '')} | {c.get('cost', 0):.3f} | {reasons} |")
    return "\n".join(lines) + "\n"


def write(cells: list[dict], out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    md_path = os.path.join(out_dir, f"report-{stamp}.md")
    json_path = os.path.join(out_dir, f"report-{stamp}.json")
    open(md_path, "w", encoding="utf-8").write(render_markdown(cells))
    open(json_path, "w", encoding="utf-8").write(json.dumps(cells, indent=2))
    return {"markdown": md_path, "json": json_path}

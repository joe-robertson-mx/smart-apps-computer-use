import json
from prompt_lab.report import render_markdown, write


def _cells():
    return [
        {"variant": "warranty_v1", "scenario": "warranty-wheel-replacement",
         "model": "sonnet-4-5", "passed": True, "steps": 6, "cost": 0.01, "reasons": []},
        {"variant": "warranty_v1", "scenario": "warranty-wheel-replacement",
         "model": "opus-4-7", "passed": False, "steps": 12, "cost": 0.30,
         "reasons": ["Status left as Pending"]},
    ]


def test_render_markdown_has_rows_and_passrate():
    md = render_markdown(_cells())
    assert "warranty_v1" in md
    assert "sonnet-4-5" in md and "opus-4-7" in md
    assert "Status left as Pending" in md
    assert "50%" in md  # 1 of 2 passed


def test_write_emits_md_and_json(tmp_path):
    paths = write(_cells(), str(tmp_path))
    assert paths["markdown"].endswith(".md")
    assert paths["json"].endswith(".json")
    data = json.loads(open(paths["json"], encoding="utf-8").read())
    assert len(data) == 2

import json
import os

from scenario_control import ControlHandler, FakeLauncher


def test_setup_clears_records_and_launches(tmp_path):
    data_dir = tmp_path
    (data_dir / "warranty_cases.json").write_text(json.dumps([{"old": 1}]), encoding="utf-8")
    launcher = FakeLauncher()
    handler = ControlHandler(data_dir=str(data_dir), launcher=launcher)

    code, body = handler.handle("/control/setup", "POST",
                                {"app": "warranty", "case": {"case_id": "EQ-2026-0042"}})
    assert code == 200
    assert body["ready"] is True
    assert body["baseline_count"] == 0
    assert json.loads((data_dir / "warranty_cases.json").read_text()) == []
    assert launcher.started == [("warranty", {"case_id": "EQ-2026-0042"})]


def test_records_returns_file_contents(tmp_path):
    (tmp_path / "dispatch_records.json").write_text(json.dumps([{"reference": "DSP-1"}]), encoding="utf-8")
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/records?app=returns", "GET", None)
    assert code == 200
    assert body["count"] == 1
    assert body["records"][0]["reference"] == "DSP-1"


def test_health(tmp_path):
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/health", "GET", None)
    assert code == 200 and body["ok"] is True


def test_unknown_path_404(tmp_path):
    handler = ControlHandler(data_dir=str(tmp_path), launcher=FakeLauncher())
    code, body = handler.handle("/control/nope", "GET", None)
    assert code == 404

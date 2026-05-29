from prompt_lab.control_client import ControlClient


def test_setup_posts_app_and_case():
    captured = {}

    def fake_transport(method, url, payload):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"ready": True, "baseline_count": 0}

    c = ControlClient("http://host:8081", transport=fake_transport)
    out = c.setup("warranty", {"case_id": "EQ-2026-0042"})
    assert captured["method"] == "POST"
    assert captured["url"] == "http://host:8081/control/setup"
    assert captured["payload"] == {"app": "warranty", "case": {"case_id": "EQ-2026-0042"}}
    assert out["baseline_count"] == 0


def test_records_gets_app_records():
    def fake_transport(method, url, payload):
        assert method == "GET"
        assert url == "http://host:8081/control/records?app=returns"
        return {"records": [{"x": 1}], "count": 1}

    c = ControlClient("http://host:8081", transport=fake_transport)
    out = c.records("returns")
    assert out["count"] == 1

from prompt_lab.executor_client import ExecutorClient, ExecResult


def test_act_posts_tool_input_and_parses_success():
    captured = {}

    def fake_transport(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"output": "Action completed", "base64image": "AAAA"}

    client = ExecutorClient("http://host:8081", transport=fake_transport)
    res = client.act({"action": "left_click", "coordinate": [10, 20]})

    assert captured["url"] == "http://host:8081/computer_tool"
    assert captured["payload"] == {"action": "left_click", "coordinate": [10, 20]}
    assert isinstance(res, ExecResult)
    assert res.output == "Action completed"
    assert res.image_b64 == "AAAA"
    assert res.error is None


def test_act_parses_error_response():
    def fake_transport(url, payload):
        return {"error_message": "boom"}

    res = ExecutorClient("http://h:8081", transport=fake_transport).act({"action": "screenshot"})
    assert res.error == "boom"
    assert res.output is None

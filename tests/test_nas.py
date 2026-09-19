"""Offline Gateway routing and LAN security regression tests."""
import json
import threading
from http.server import ThreadingHTTPServer

import httpx
import pytest

from jev_ultrafast import demo, model
from jev_ultrafast.providers import decision_endpoint, secret


def test_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("JEV_PROVIDER", "unknown")
    with pytest.raises(ValueError):
        decision_endpoint()
    monkeypatch.setenv("JEV_PROVIDER", "vercel")
    monkeypatch.setenv("TYPESAFE_API_KEY", "must-not-be-used")
    assert decision_endpoint() == ("http://127.0.0.1:8767/evaluate", "", "typesafe-ai/jev")


def test_docker_secret_precedence(monkeypatch, tmp_path):
    path = tmp_path / "key"
    path.write_text("file-key\n")
    monkeypatch.setenv("TEST_KEY_FILE", str(path))
    assert secret("TEST_KEY") == "file-key"
    monkeypatch.setenv("TEST_KEY", "env-key")
    assert secret("TEST_KEY") == "env-key"


def test_text_gateway_key_and_tags(monkeypatch):
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-gateway-key")
    monkeypatch.setenv("TEXT_MODEL", "configurable-model")

    def post(url, key, body):
        assert url == "https://ai-gateway.vercel.sh/v1/chat/completions"
        assert key == "test-gateway-key"
        assert body["model"] == "configurable-model"
        assert body["response_format"] == {"type": "json_object"}
        assert body["reasoning_effort"] == "none"
        assert body["providerOptions"]["gateway"]["tags"][-1] == "component:type-text"
        return {"choices": [{"message": {"content": json.dumps({"text": "Gödel"})}}]}

    monkeypatch.setattr(model, "post_json", post)
    assert model.field_text({})[0] == "Gödel"


@pytest.mark.parametrize("origin", ["*", "http://nas:8766/", "http://user:pass@nas:8766", "http://nas/#x"])
def test_invalid_public_origin(monkeypatch, origin):
    monkeypatch.setenv("JEV_PUBLIC_ORIGIN", origin)
    with pytest.raises(ValueError):
        demo.configure_hosting()


def test_lan_host_origin_and_token(monkeypatch):
    monkeypatch.setattr(demo, "AUTHORITY", "192.168.50.115:8766")
    monkeypatch.setattr(demo, "ORIGIN", "http://192.168.50.115:8766")
    monkeypatch.setattr(demo, "command", lambda *_: {"ok": True})
    server = ThreadingHTTPServer(("127.0.0.1", 0), demo.Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        headers = {"Host": demo.AUTHORITY, "Origin": demo.ORIGIN, "X-Demo-Token": demo.TOKEN}
        with httpx.Client() as client:
            assert client.get(url, headers=headers).status_code == 200
            assert client.get(url + "/healthz", headers=headers).status_code == 200
            assert client.get(url, headers={"Host": "evil.test"}).status_code == 403
            assert client.post(url + "/api/reset", json={}, headers=headers).status_code == 200
            for bad in ({"Host": "evil.test"}, {"Origin": "http://evil.test"}, {"X-Demo-Token": "bad"}):
                assert client.post(url + "/api/reset", json={}, headers={**headers, **bad}).status_code == 403
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_custom_start_url_and_reject_executable_url(monkeypatch):
    from unittest.mock import Mock

    fake = Mock()
    monkeypatch.setattr(demo, "Agent", fake)
    monkeypatch.setattr(demo, "close_browser", lambda: None)
    monkeypatch.setattr(demo, "response_state", lambda: {})
    monkeypatch.setattr(demo, "AGENT", None)
    fake.return_value.state = {}
    demo.command("reset", {"scenario": "wikipedia", "goal": "Read a page", "url": "https://example.test/"})
    assert fake.call_args.args[:2] == ("https://example.test/", "Read a page")
    fake.reset_mock()
    with pytest.raises(ValueError):
        demo.command("reset", {"goal": "Read a page", "url": "javascript:alert(1)"})
    fake.assert_not_called()

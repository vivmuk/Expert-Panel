import pytest

from server.api.chat import TURN_LIMIT, admit_engagement
from server.chatjob import handle_turn
from server.venice.client import CHAT_TIMEOUT, MAX_ATTEMPTS, VeniceClient
from server.venice.errors import VeniceError

PARTNER = {"Authorization": "Bearer partner-test-key"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    from server import create_app

    return create_app().test_client()


def _turn(client, chat_id, real_ip, spoof="198.51.100.1"):
    return client.post(
        "/api/chat",
        json={"message": "", "state": {"chat_id": chat_id}},
        headers={"X-Forwarded-For": f"{spoof}, {real_ip}"},
    )


def test_a_spoofed_first_forwarded_hop_does_not_escape_the_rate_limit(client):
    for n in range(TURN_LIMIT):
        assert _turn(client, "xff", "203.0.113.7", spoof=f"198.51.100.{n}").status_code == 200
    blocked = _turn(client, "xff", "203.0.113.7", spoof="198.51.100.250")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "rate"
    assert _turn(client, "xff", "203.0.113.8").status_code == 200


def test_chat_refuses_with_503_when_no_signing_secret_is_set(client, monkeypatch):
    monkeypatch.delenv("AI_PARTNER_SIGNING_SECRETS", raising=False)
    monkeypatch.delenv("AI_PARTNER_SIGNING_SECRET", raising=False)
    res = client.post("/api/chat", json={"message": "Pricing for a B2B analytics product", "state": {}})
    assert res.status_code == 503
    assert res.get_json()["error"]["code"] == "not_configured"
    assert "AI_PARTNER_SIGNING_SECRETS" in res.get_json()["reply"]
    artifact = client.post("/api/chat/artifact", json={"artifact_id": "research-brief", "state": {}})
    assert artifact.status_code == 503
    direct = handle_turn({"calls": 0}, "Pricing for a B2B analytics product", lambda *a: {})
    assert direct["error"]["code"] == "not_configured"
    v1 = client.post("/v1/chat/completions", json={"model": "ai-partner", "messages": [{"role": "user", "content": "Hi"}]}, headers=PARTNER)
    assert v1.status_code == 503


def test_new_engagements_are_capped_per_ip_per_day(client, monkeypatch):
    monkeypatch.setenv("AI_PARTNER_DAILY_ENGAGEMENTS", "2")
    assert _turn(client, "first", "203.0.113.9").status_code == 200
    assert _turn(client, "second", "203.0.113.9", spoof="198.51.100.2").status_code == 200
    third = _turn(client, "third", "203.0.113.9", spoof="198.51.100.3")
    assert third.status_code == 429
    assert third.get_json()["error"]["code"] == "daily_limit"
    assert client.post("/api/chat", json={"message": "", "state": {}}, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 429
    assert _turn(client, "first", "203.0.113.9").status_code == 200
    assert _turn(client, "third", "203.0.113.10").status_code == 200
    assert admit_engagement("203.0.113.9", "third", now=10**12)


def test_every_response_carries_the_security_headers(client):
    for method, path in (("get", "/chat"), ("get", "/health"), ("get", "/api/catalog"), ("get", "/demos/maritime/deck"),
                         ("get", "/no-such-page"), ("post", "/mcp"), ("get", "/img/brand/avatar.webp")):
        res = getattr(client, method)(path)
        assert res.headers["Content-Security-Policy"] == "frame-ancestors 'self'", path
        assert res.headers["X-Frame-Options"] == "SAMEORIGIN", path
        assert res.headers["X-Content-Type-Options"] == "nosniff", path
        assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin", path


class _Resp:
    def __init__(self, status, content="not json"):
        self.status_code = status
        self.text = content
        self.headers = {}
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}], "usage": {}}


def _venice(monkeypatch, responses):
    client = VeniceClient(api_key="test-not-a-real-key")
    seen = []

    def request(method, url, json=None, timeout=None, stream=False):
        seen.append(timeout)
        return responses[min(len(seen), len(responses)) - 1]

    monkeypatch.setattr(client._session, "request", request)
    monkeypatch.setattr("server.venice.client.time.sleep", lambda _s: None)
    return client, seen


@pytest.mark.parametrize(
    "responses",
    [
        [_Resp(503)],
        [_Resp(503), _Resp(503), _Resp(200)],
        [_Resp(200), _Resp(503)],
    ],
)
def test_one_structured_call_makes_at_most_three_upstream_requests(monkeypatch, responses):
    client, seen = _venice(monkeypatch, responses)
    with pytest.raises(VeniceError):
        client.structured("model", [{"role": "user", "content": "Hi"}], "Chat", {"type": "object"})
    assert len(seen) == MAX_ATTEMPTS == 3
    assert set(seen) == {CHAT_TIMEOUT} == {90}


def test_the_thinking_off_retry_still_runs_inside_the_cap(monkeypatch):
    client, seen = _venice(monkeypatch, [_Resp(200), _Resp(200, '{"ok": true}')])
    assert client.structured("model", [{"role": "user", "content": "Hi"}], "Chat", {"type": "object"}) == {"ok": True}
    assert len(seen) == 2


def _init(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, headers=PARTNER)
    return res.headers["Mcp-Session-Id"]


def test_mcp_accepts_only_session_ids_it_issued(client):
    session = _init(client)
    ok = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers={**PARTNER, "Mcp-Session-Id": session})
    assert ok.status_code == 200
    forged_id = "0" * 32 + "." + session.split(".")[1]
    for bad in ("made-up", session.split(".")[0], forged_id, session + "x"):
        res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, headers={**PARTNER, "Mcp-Session-Id": bad})
        assert res.status_code == 404, bad


def test_v1_rejects_an_unknown_model(client):
    res = client.post("/v1/chat/completions", json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}, headers=PARTNER)
    assert res.status_code == 400
    assert res.get_json()["error"]["type"] == "invalid_request_error"


def test_unknown_pages_get_a_styled_404_and_api_paths_get_json(client):
    page = client.get("/definitely/not/here")
    assert page.status_code == 404
    assert page.mimetype == "text/html"
    body = page.get_data(as_text=True)
    assert "This page isn't here." in body and 'href="/chat"' in body and "/app.css" in body
    api = client.get("/api/definitely-not-here")
    assert api.status_code == 404 and api.get_json()["error"]["code"] == "not_found"

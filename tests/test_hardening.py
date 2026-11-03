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


def test_on_railway_the_edge_set_real_ip_is_the_key_and_forwarded_for_is_ignored(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")

    def edge(n, real="203.0.113.20"):
        return client.post(
            "/api/chat",
            json={"message": "", "state": {"chat_id": "edge"}},
            headers={"X-Forwarded-For": f"198.51.100.{n}", "X-Real-IP": real},
        )

    for n in range(TURN_LIMIT):
        assert edge(n).status_code == 200
    assert edge(99).get_json()["error"]["code"] == "rate"
    assert edge(100, real="203.0.113.21").status_code == 200


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


def test_malformed_json_is_rejected(client):
    res = client.post("/api/chat", data=b"not-json", content_type="application/json")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "bad_request"
    assert "Traceback" not in res.get_data(as_text=True)
    empty = client.post("/api/chat", data=b"", content_type="application/json")
    assert empty.status_code == 200


def test_oversized_body_is_413_without_a_traceback(client):
    from server import MAX_BODY_BYTES

    res = client.post("/api/chat", data=b"{" + b"x" * (MAX_BODY_BYTES + 8), content_type="application/json")
    assert res.status_code == 413
    body = res.get_data(as_text=True)
    assert "Traceback" not in body
    assert res.get_json()["error"]["code"] == "too_large"


def test_stateless_chat_refuses_when_no_signing_secret_is_set(client, monkeypatch):
    monkeypatch.delenv("AI_PARTNER_SIGNING_SECRETS", raising=False)
    monkeypatch.delenv("AI_PARTNER_SIGNING_SECRET", raising=False)
    called = []
    monkeypatch.setattr("server.api.chat.complete_with_venice", lambda *a, **k: called.append(1))
    res = client.post("/chat", json={"message": "Market entry into Germany"})
    assert res.status_code == 503
    assert called == []
    assert "Traceback" not in res.get_data(as_text=True)


def test_two_tabs_cannot_both_spend_the_last_call():
    import threading

    from server.budget import sign_calls
    from server.chatjob import MAX_MODEL_CALLS, handle_turn

    calls = []
    started = threading.Event()
    release = threading.Event()

    def complete(name, messages, schema, max_tokens):
        calls.append(name)
        started.set()
        assert release.wait(2)
        return {"facts": ["Germany."], "service_line": "Market entry", "queries": ["German reimbursement"]}

    raw = {
        "chat_id": "two-tabs",
        "problem": "Market entry for a medtech device into Germany.",
        "team": "4 analysts",
        "tools": "Excel",
        "maturity": 2,
        "calls": MAX_MODEL_CALLS - 1,
        "sig": sign_calls("two-tabs", MAX_MODEL_CALLS - 1),
    }
    results = []

    def run():
        results.append(handle_turn(dict(raw), "", complete, search=lambda *a, **k: []))

    threads = [threading.Thread(target=run), threading.Thread(target=run)]
    for thread in threads:
        thread.start()
    assert started.wait(2)
    release.set()
    for thread in threads:
        thread.join(3)
    assert len(calls) == 1
    codes = [(item.get("error") or {}).get("code") for item in results]
    assert sorted(code or "" for code in codes) == ["", "budget"]
    assert max(item["state"]["calls"] for item in results) == MAX_MODEL_CALLS


def test_v1_stops_at_the_rate_limit_before_a_second_model_call(client, monkeypatch):
    monkeypatch.setattr("server.api.chat.TURN_LIMIT", 1)
    called = []

    def complete(name, messages, schema, max_tokens):
        called.append(name)
        return {"facts": ["Germany."], "service_line": "Market entry", "queries": ["pricing"]}

    monkeypatch.setattr("server.api.agents.complete_with_venice", complete)
    monkeypatch.setattr("server.api.agents.exa_search", lambda *a, **k: [])
    body = {"model": "ai-partner", "messages": [{"role": "user", "content": "Market entry into Germany. Team: 4 analysts. Tools: Excel. Maturity 2."}]}
    first = client.post("/v1/chat/completions", json=body, headers=PARTNER)
    assert first.status_code == 200
    second = client.post("/v1/chat/completions", json=body, headers=PARTNER)
    assert second.status_code == 429
    assert second.get_json()["error"]["type"] == "rate"
    assert called == ["ChatResearch"]


def test_v1_stream_and_json_return_the_allowlisted_model(client):
    body = {"model": "ai-partner", "messages": [{"role": "user", "content": "Hi"}]}
    quiet = client.post("/v1/chat/completions", json={**body, "stream": False}, headers=PARTNER)
    assert quiet.status_code == 200
    assert quiet.get_json()["model"] == "ai-partner"
    streamed = client.post("/v1/chat/completions", json={**body, "stream": True}, headers=PARTNER)
    assert streamed.status_code == 200
    assert streamed.mimetype == "text/event-stream"
    text = streamed.get_data(as_text=True)
    assert "data: [DONE]" in text
    assert '"model": "ai-partner"' in text


def test_forged_and_bad_keys_are_rejected(client):
    body = {"model": "ai-partner", "messages": [{"role": "user", "content": "Hi"}]}
    for token in ("", "garbage", "ap_forged.not-a-real-signature"):
        res = client.post("/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401, token
        assert res.get_json()["error"]["message"] == "invalid or missing API key"
        mcp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={"Authorization": f"Bearer {token}"})
        assert mcp.status_code == 401, token


def test_model_list_does_not_return_the_upstream_body(client, monkeypatch):
    from server.venice.errors import VeniceError

    class Boom:
        def summary(self):
            raise VeniceError("HTTP 500 from /models: UPSTREAM_BODY_LEAK_TOKEN", 500, "UPSTREAM_BODY_LEAK_TOKEN")

    monkeypatch.setattr("server.api.meta.get_catalog", lambda: Boom())
    res = client.get("/api/models")
    assert res.status_code == 502
    text = res.get_data(as_text=True)
    assert "UPSTREAM_BODY_LEAK_TOKEN" not in text
    assert "Traceback" not in text
    assert res.get_json()["error"]["message"] == "The model list is unavailable right now."


def test_unknown_pages_get_a_styled_404_and_api_paths_get_json(client):
    page = client.get("/definitely/not/here")
    assert page.status_code == 404
    assert page.mimetype == "text/html"
    body = page.get_data(as_text=True)
    assert "This page isn't here." in body and 'href="/chat"' in body and "/app.css" in body
    api = client.get("/api/definitely-not-here")
    assert api.status_code == 404 and api.get_json()["error"]["code"] == "not_found"

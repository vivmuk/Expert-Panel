import hashlib
import hmac
import json
import time

import pytest

SECRET = "whsec_test"


def _sign(raw, ts=None):
    ts = ts or int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


PAYLOAD = {
    "type": "keiki.turn",
    "version": 1,
    "turnId": "turn-1",
    "agentId": "agent-1",
    "conversationId": "+15555550123",
    "messages": [{"text": "We run a clinic", "content": "We run a clinic"}],
    "keiki": {"turnUrl": "https://keiki.example/api/v1/turns/turn-1"},
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KEIKI_HARNESS_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("KEIKI_AGENT_ID", "agent-1")
    from server import create_app

    return create_app().test_client()


def test_rejects_unsigned_and_stale(client):
    raw = json.dumps(PAYLOAD).encode()
    assert client.post("/keiki/turn", data=raw, content_type="application/json").status_code == 401
    old = _sign(raw, int(time.time()) - 3600)
    r = client.post("/keiki/turn", data=raw, content_type="application/json", headers={"Keiki-Signature": old})
    assert r.status_code == 401


def test_not_configured(monkeypatch, client):
    monkeypatch.delenv("KEIKI_HARNESS_SIGNING_SECRET")
    assert client.post("/keiki/turn", data=b"{}").status_code == 503


def test_wrong_agent(client):
    raw = json.dumps(dict(PAYLOAD, agentId="other")).encode()
    r = client.post("/keiki/turn", data=raw, content_type="application/json",
                    headers={"Keiki-Signature": _sign(raw), "Keiki-Turn-Token": "ht_x"})
    assert r.status_code == 401


def test_turn_runs_engine_and_replies(monkeypatch, client):
    from server.api import keiki

    calls = []
    monkeypatch.setattr(keiki, "_engine", lambda m, s: {"reply": "Hi " + m, "state": {"n": 1}})
    monkeypatch.setattr(keiki, "_post", lambda url, tok, body: calls.append((url, tok, body)))
    started = []
    monkeypatch.setattr(keiki.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: started.append(target(*args))})())
    raw = json.dumps(PAYLOAD).encode()
    r = client.post("/keiki/turn", data=raw, content_type="application/json",
                    headers={"Keiki-Signature": _sign(raw), "Keiki-Turn-Token": "ht_x"})
    assert r.status_code == 202
    assert calls[0][0].endswith("/turns/turn-1/messages") and calls[0][2]["text"] == "Hi We run a clinic"
    assert calls[0][1] == "ht_x"
    assert calls[-1][0].endswith("/complete") and calls[-1][2] == {"status": "completed"}
    assert keiki._states[("agent-1", "+15555550123")] == {"n": 1}


def test_engine_failure_completes_failed(monkeypatch):
    from server.api import keiki

    calls = []
    monkeypatch.setattr(keiki, "_engine", lambda m, s: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(keiki, "_post", lambda url, tok, body: calls.append(body))
    keiki.run_turn(PAYLOAD, "ht_x")
    assert calls[-1]["status"] == "failed"


def test_cancellation_accepted(client):
    raw = json.dumps({"type": "keiki.turn.cancelled", "turnId": "t", "agentId": "agent-1"}).encode()
    r = client.post("/keiki/turn", data=raw, content_type="application/json", headers={"Keiki-Signature": _sign(raw)})
    assert r.status_code == 202


def test_strip_is_honest(monkeypatch, client):
    monkeypatch.delenv("KEIKI_LIVE_CHANNELS", raising=False)
    html = client.get("/chat").get_data(as_text=True)
    assert "keiki-strip" in html and "Coming soon:</span> iMessage, WhatsApp" in html and "Live:" not in html
    monkeypatch.setenv("KEIKI_LIVE_CHANNELS", "telegram,email")
    html = client.get("/chat").get_data(as_text=True)
    assert "<b>Live:</b> Telegram, email" in html

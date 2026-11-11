"""Paid routes stay closed. A configured integer is not a bill.

The transport cases call VeniceClient against a local socket or a stubbed
session. They do not call a provider.
"""
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from server.spendguard import SpendClosed, claim_send
from server.venice.client import VeniceClient
from server.venice.errors import AmbiguousSend, VeniceError
from tests.test_chatjob import ONE_SHOT


class Boom(Exception):
    pass


@pytest.fixture
def provider_spies(monkeypatch):
    calls = []

    def boom(*_args, **_kwargs):
        calls.append("network")
        raise AssertionError("provider I/O")

    monkeypatch.setattr("server.venice.client.requests.Session.request", boom)
    monkeypatch.setattr("server.exa_search.requests.post", boom)
    monkeypatch.setattr("server.chatmemory.requests.post", boom)
    return calls


def _client():
    from server import create_app

    return create_app().test_client()


def _prices(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER", "sqlite")
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER_PATH", str(tmp_path / "spend.db"))
    monkeypatch.setenv("AI_PARTNER_CALCULATED_CEILING_MICROUSD", "1000000")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_VENICE_ATTEMPT", "10")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_EXA", "4")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_MEMORY", "7")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_VOICE", "10")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_IMAGE", "10")


def test_unpaid_intake_does_not_call_a_provider(provider_spies):
    res = _client().post("/api/chat", json={"message": "We make parts for machines.", "state": {}})
    body = res.get_json()
    assert res.status_code == 200
    assert body["state"]["phase"] == "ask_context"
    assert body.get("error") is None
    assert provider_spies == []


def test_configured_prices_do_not_open_paid_routes(provider_spies, monkeypatch, tmp_path):
    _prices(monkeypatch, tmp_path)
    monkeypatch.setenv("VENICE_API_KEY", "present")
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "present")
    client = _client()
    stateless = client.post("/chat", json={"message": "Hello from a channel", "source": "maritime"})
    assert stateless.status_code == 403
    assert stateless.get_json()["error"]["code"] == "currency_bound_unavailable"
    voice = client.post("/api/voice/plan", json={"text": "open the deck"})
    assert voice.status_code == 403
    models = client.get("/api/models")
    estimate = client.post("/api/estimate", json={"mode": "deep_dive", "panelSize": 20})
    assert models.status_code == 403 and estimate.status_code == 403
    from server.api.branding import _generate_slot

    with pytest.raises(SpendClosed) as brand:
        _generate_slot("hero", prompt="other", model="other-model")
    assert brand.value.code == "currency_bound_unavailable"
    from server.exa_search import exa_search
    from server.chatmemory import recall

    with pytest.raises(SpendClosed):
        exa_search("margin")
    with pytest.raises(SpendClosed):
        recall("chat", "query")
    assert provider_spies == []
    paid = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert paid.status_code != 403
    assert paid.get_json()["error"]["code"] != "currency_bound_unavailable"
    assert provider_spies
    held = len(provider_spies)
    artifact = client.post(
        "/api/chat/artifact",
        json={"artifact_id": "research-brief", "state": {"problem": "Parts", "phase": "done"}},
    )
    assert artifact.status_code != 403
    assert len(provider_spies) > held


def test_legacy_run_and_auth_boundary(provider_spies, monkeypatch):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "static-test-key")
    client = _client()
    missing = client.post("/api/runs", json={"input": {"problem": "A hypothetical plant network."}})
    assert missing.status_code == 401
    present = client.post(
        "/api/runs",
        json={"input": {"problem": "A hypothetical plant network."}},
        headers={"Authorization": "Bearer static-test-key"},
    )
    assert present.status_code == 403
    assert present.get_json()["error"]["code"] == "paid_path_blocked"
    assert provider_spies == []


def test_forged_signature_is_rejected_before_a_provider(provider_spies):
    res = _client().post(
        "/api/chat",
        json={
            "message": "",
            "state": {
                "chat_id": "fixedchat0000001",
                "phase": "research",
                "problem": "Hypothetical plant margins.",
                "team": "finance",
                "tools": "spreadsheets",
                "maturity": 2,
                "calls": 3,
                "sig": "v1.not-a-signature",
            },
        },
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "tamper"
    assert provider_spies == []


def test_research_phase_without_a_signature_does_not_call_a_provider(provider_spies):
    res = _client().post(
        "/api/chat",
        json={
            "message": "",
            "state": {
                "chat_id": "fixedchat0000001",
                "phase": "research",
                "problem": "Hypothetical plant margins.",
                "team": "finance",
                "tools": "spreadsheets",
                "maturity": 2,
                "calls": 0,
            },
        },
    )
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "currency_bound_unavailable"
    assert provider_spies == []


def test_v1_and_mcp_paid_tools_stay_closed(provider_spies, monkeypatch):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "static-test-key")
    client = _client()
    headers = {"Authorization": "Bearer static-test-key"}
    anonymous = client.post(
        "/v1/chat/completions",
        json={"model": "ai-partner", "messages": [{"role": "user", "content": ONE_SHOT}]},
    )
    assert anonymous.status_code == 401
    paid = client.post(
        "/v1/chat/completions",
        json={"model": "ai-partner", "messages": [{"role": "user", "content": ONE_SHOT}]},
        headers=headers,
    )
    assert paid.status_code == 200
    text = paid.get_json()["choices"][0]["message"]["content"]
    assert "not sent" in text.lower() or "Paid work is stopped" in text
    session = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        headers=headers,
    ).headers["Mcp-Session-Id"]
    tool = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "start_job", "arguments": {"message": ONE_SHOT}},
        },
        headers={**headers, "Mcp-Session-Id": session},
    )
    assert tool.status_code == 200
    body = tool.get_json()["result"]["content"][0]["text"]
    assert "Paid work is stopped" in body
    assert provider_spies == []


def test_signed_keiki_turn_does_not_call_a_provider(provider_spies, monkeypatch):
    monkeypatch.setenv("KEIKI_HARNESS_SIGNING_SECRET", "whsec_test")
    monkeypatch.setenv("KEIKI_AGENT_ID", "agent-1")
    from server.api import keiki

    posted = []
    monkeypatch.setattr(keiki, "_post", lambda url, token, body: posted.append(body))
    keiki.reset_replays()
    raw = json.dumps(
        {
            "type": "keiki.turn",
            "turnId": "closed-1",
            "agentId": "agent-1",
            "conversationId": "conv-1",
            "messages": [{"text": ONE_SHOT}],
            "keiki": {"turnUrl": "https://keiki.example/turns/closed-1"},
        }
    ).encode()
    ts = int(time.time())
    sig = hmac.new(b"whsec_test", f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    bad = _client().post("/keiki/turn", data=raw, headers={"Content-Type": "application/json"})
    assert bad.status_code == 401
    accepted = _client().post(
        "/keiki/turn",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "Keiki-Signature": f"t={ts},v1={sig}",
            "Keiki-Turn-Token": "ht_x",
        },
    )
    assert accepted.status_code == 202
    for _ in range(50):
        if any(item.get("status") == "completed" for item in posted):
            break
        time.sleep(0.02)
    assert any("Paid work is stopped" in str(item.get("text") or "") for item in posted)
    assert provider_spies == []


def test_direct_client_without_a_journal_does_not_send(provider_spies):
    client = VeniceClient(journal_path=None)
    with pytest.raises(SpendClosed) as exc:
        client.structured("model", [{"role": "user", "content": "Hi"}], "Chat", {"type": "object"})
    assert exc.value.code == "currency_bound_unavailable"
    with pytest.raises(SpendClosed):
        claim_send(":memory:", "k")
    with pytest.raises(SpendClosed):
        claim_send("relative.db", "k")
    assert provider_spies == []


class _Drop(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("Content-Length") or 0)
        if size:
            self.rfile.read(size)
        self.server.hits += 1
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def log_message(self, *_args):
        return


def _drop_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Drop)
    httpd.hits = 0
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _one_call(client):
    return client.structured(
        "model",
        [{"role": "user", "content": "Hi"}],
        "Chat",
        {"type": "object"},
        temperature=0,
        max_completion_tokens=20,
    )


def test_ambiguous_local_response_is_received_once_and_skips_repair(tmp_path):
    """httpd.hits counts HTTP requests the local server received, not a provider charge."""
    httpd = _drop_server()
    try:
        client = VeniceClient(
            base_url=f"http://127.0.0.1:{httpd.server_port}",
            timeout=1,
            journal_path=str(tmp_path / "transport.db"),
        )
        with pytest.raises(AmbiguousSend):
            _one_call(client)
        assert httpd.hits == 1
        with pytest.raises(SpendClosed) as again:
            _one_call(client)
        assert again.value.code == "phase_uncertain"
        assert httpd.hits == 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_an_intact_uncertain_row_is_visible_to_a_new_process(tmp_path):
    """The file is left in place. This is not a replacement or truncation test."""
    httpd = _drop_server()
    saved = tmp_path / "kept.db"
    try:
        fresh = VeniceClient(
            base_url=f"http://127.0.0.1:{httpd.server_port}",
            timeout=1,
            journal_path=str(saved),
        )
        with pytest.raises(AmbiguousSend):
            _one_call(fresh)
        assert httpd.hits == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.spendguard import SpendClosed
from server.venice.client import VeniceClient
client = VeniceClient(api_key="t", base_url="http://127.0.0.1:9", timeout=1, journal_path=os.environ["JOURNAL"])
try:
    client.structured("model", [{"role": "user", "content": "Hi"}], "Chat", {"type": "object"}, temperature=0, max_completion_tokens=20)
    print("SENT")
except SpendClosed as exc:
    print(exc.code)
"""
    env = {**os.environ, "REPO": os.getcwd(), "JOURNAL": str(saved)}
    completed = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "phase_uncertain"


def _fresh_claim(path, op):
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.spendguard import SpendClosed, claim_send
try:
    claim_send(os.environ["JOURNAL"], os.environ["OP"])
    print("CLAIMED")
except SpendClosed as exc:
    print(exc.code)
"""
    env = {**os.environ, "REPO": os.getcwd(), "JOURNAL": str(path), "OP": op}
    completed = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_replacement_and_truncate_are_unsolved_across_a_new_process(tmp_path):
    """Process-local inode and lost-key sets do not survive a new process."""
    from server.spendguard import claim_send, lose_send

    replaced = tmp_path / "replaced.db"
    claim_send(str(replaced), "same-op")
    lose_send(str(replaced), "same-op")
    replaced.unlink()
    for suffix in ("-wal", "-shm"):
        extra = tmp_path / f"replaced.db{suffix}"
        if extra.exists():
            extra.unlink()
    replaced.write_bytes(b"")
    assert _fresh_claim(replaced, "same-op") == "CLAIMED"

    truncated = tmp_path / "truncated.db"
    claim_send(str(truncated), "pending-op")
    inode = truncated.stat().st_ino
    for suffix in ("-wal", "-shm"):
        extra = tmp_path / f"truncated.db{suffix}"
        if extra.exists():
            extra.unlink()
    os.truncate(truncated, 0)
    assert truncated.stat().st_ino == inode
    assert _fresh_claim(truncated, "pending-op") == "CLAIMED"


def test_a_definite_invalid_json_response_still_repairs_inside_one_call(monkeypatch, tmp_path):
    seen = []

    class Resp:
        def __init__(self, content):
            self.status_code = 200
            self.text = content
            self.headers = {}

        def json(self):
            return {"choices": [{"message": {"content": self.text}}], "usage": {}}

    def request(method, url, json=None, timeout=None, stream=False):
        seen.append(json["messages"][-1]["content"])
        if len(seen) == 1:
            return Resp("not json")
        return Resp('{"ok": true}')

    client = VeniceClient(journal_path=str(tmp_path / "repair.db"))
    monkeypatch.setattr(client._session, "request", request)
    assert _one_call(client) == {"ok": True}
    assert len(seen) == 2
    assert "valid JSON" in seen[1]


def test_stream_true_is_refused_before_a_hold_or_a_socket(monkeypatch, tmp_path):
    path = tmp_path / "stream.db"
    seen = []

    def request(*_args, **_kwargs):
        seen.append("socket")
        raise AssertionError("stream reached the socket")

    client = VeniceClient(journal_path=str(path))
    monkeypatch.setattr(client._session, "request", request)
    with pytest.raises(SpendClosed) as exc:
        client._request("POST", "/chat/completions", json_body={"stream": True}, stream=True)
    assert exc.value.code == "paid_path_blocked"
    assert seen == []
    assert not path.exists()


def test_a_completed_hold_can_be_claimed_again(tmp_path):
    from server.spendguard import claim_send, release_send

    path = str(tmp_path / "released.db")
    claim_send(path, "op")
    release_send(path, "op")
    claim_send(path, "op")


def test_failed_uncertain_update_blocks_only_this_process(tmp_path):
    import sqlite3

    from server import spendguard

    path = str(tmp_path / "hold.db")
    claim_send(path, "op")
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM send_hold")
    conn.commit()
    conn.close()
    with pytest.raises(SpendClosed) as lost:
        spendguard.lose_send(path, "op")
    assert lost.value.code == "phase_uncertain"
    with pytest.raises(SpendClosed) as blocked:
        claim_send(path, "op")
    assert blocked.value.code == "phase_uncertain"
    assert _fresh_claim(path, "op") == "CLAIMED"

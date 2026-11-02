import json
import threading

import pytest
from werkzeug.serving import make_server

from server.config import Config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("AI_PARTNER_API_KEYS", raising=False)
    from server import create_app

    return create_app().test_client()


@pytest.fixture
def keyed(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    return create_app().test_client()


def test_agent_endpoints_reject_missing_keys(client):
    denied = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert denied.status_code == 401
    assert "AI_PARTNER_API_KEYS" in denied.get_json()["error"]["message"]
    denied = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert denied.status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/chat").status_code == 200


def test_mcp_handshake_and_start_job(keyed):
    headers = {"Authorization": "Bearer partner-test-key", "Accept": "application/json"}
    init = keyed.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )
    assert init.status_code == 200
    body = init.get_json()
    assert body["result"]["protocolVersion"] == "2025-03-26"
    assert body["result"]["serverInfo"]["name"] == "AI Partner"
    session = init.headers["Mcp-Session-Id"]
    note = keyed.post(
        "/mcp",
        headers={**headers, "Mcp-Session-Id": session},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert note.status_code == 202
    listed = keyed.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [tool["name"] for tool in listed.get_json()["result"]["tools"]]
    assert names == ["start_job", "chat_turn", "get_work_chart", "get_kit", "get_skill_pack"]
    called = keyed.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "start_job", "arguments": {"message": "Pricing for a B2B analytics product"}},
        },
    )
    result = called.get_json()["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert "team" in payload["reply"].lower()
    assert payload["state"]["phase"] == "ask_context"
    missing = keyed.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_work_chart", "arguments": {"state": payload["state"]}},
        },
    )
    assert missing.get_json()["result"]["isError"] is True


def test_openai_sdk_against_the_chat_flow(monkeypatch, tmp_path):
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    app = create_app()
    httpd = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client = openai.OpenAI(
            base_url=f"http://127.0.0.1:{httpd.server_port}/v1",
            api_key="partner-test-key",
        )
        reply = client.chat.completions.create(
            model="ai-partner",
            messages=[{"role": "user", "content": "Pricing for a B2B analytics product"}],
        )
        assert "team" in reply.choices[0].message.content.lower()
    finally:
        httpd.shutdown()


def test_deck_links_back_to_chat(client):
    page = client.get("/deck")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert 'href="/chat"' in text
    assert "Public, no login." in text
    assert "{{DEMO_URL}}" not in text
    assert client.get("/connect").status_code == 200
    assert b"/mcp" in client.get("/connect").data

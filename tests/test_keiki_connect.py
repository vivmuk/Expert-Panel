import json

import pytest

from server.config import Config

ORIGIN = "http://localhost"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "key-one,key-two")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    return create_app().test_client()


def _call(client, key, name, arguments):
    response = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {key}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    )
    result = response.get_json()["result"]
    text = result["content"][0]["text"]
    return result["isError"], (text if result["isError"] else json.loads(text))


def test_home_page_offers_channels_without_a_status_strip(client):
    html = client.get("/chat").get_data(as_text=True)
    assert "keiki-strip" not in html
    assert 'data-open-dialog="keiki-dialog"' in html and "Put AI Partner in iMessage / WhatsApp / Slack / Telegram / email" in html
    for slug in ("imessage", "whatsapp", "slack", "telegram", "email"):
        assert f"/img/marks/channels/{slug}.svg" in html
        assert client.get(f"/img/marks/channels/{slug}.svg").status_code == 200
    assert '<dialog class="keiki-dialog" id="keiki-dialog"' in html
    assert f"Fetch {ORIGIN}/keiki.md and follow it." in html
    assert "{{secret.AI_PARTNER_API_KEY}}" in html and f"{ORIGIN}/mcp" in html
    assert "Coming soon" in html and "/keiki.js" in html
    assert client.get("/keiki.js").status_code == 200


def test_keiki_md_is_an_agent_playbook(client):
    response = client.get("/keiki.md")
    assert response.status_code == 200 and response.mimetype == "text/markdown"
    text = response.get_data(as_text=True)
    assert "HOST" not in text and "DEPLOYMENT" not in text
    assert f'curl -sS -X POST "{ORIGIN}/api/signup"' in text
    body = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert body["agent"]["features"] == {"sandbox": True, "mcp": True}
    assert body["mcp_connections"][0]["endpoint"] == f"{ORIGIN}/mcp"
    assert body["mcp_connections"][0]["headers"] == {"Authorization": "Bearer {{secret.AI_PARTNER_API_KEY}}"}
    assert "job_id" in body["agent"]["system_prompt"]
    assert "keiki.md" in client.get("/llms.txt").get_data(as_text=True)


def test_connect_page_has_the_keiki_setup(client):
    html = client.get("/connect").get_data(as_text=True)
    assert 'id="keiki"' in html and "keiki.md and follow it." in html and "Coming soon" in html


def test_mcp_job_id_keeps_state_on_the_server_per_key(client):
    error, started = _call(client, "key-one", "start_job", {"message": "Pricing for a B2B analytics product"})
    assert not error and started["job_id"].startswith("job_") and started["state"]["phase"] == "ask_context"
    error, turned = _call(client, "key-one", "chat_turn", {"job_id": started["job_id"], "message": "Four engineers on GitHub."})
    assert not error and "state" not in turned and turned["job_id"] == started["job_id"] and turned["reply"]
    error, chart = _call(client, "key-one", "get_work_chart", {"job_id": started["job_id"]})
    assert error and "not ready" in chart
    error, stolen = _call(client, "key-two", "chat_turn", {"job_id": started["job_id"], "message": "hi"})
    assert error and "Unknown or expired job_id" in stolen
    error, _ = _call(client, "key-one", "chat_turn", {"job_id": "../../etc/passwd", "message": "hi"})
    assert error


def test_mcp_state_clients_still_work(client):
    _, started = _call(client, "key-one", "start_job", {"message": "Pricing for a B2B analytics product"})
    error, turned = _call(client, "key-one", "chat_turn", {"state": started["state"], "message": "Four engineers on GitHub."})
    assert not error and "state" in turned

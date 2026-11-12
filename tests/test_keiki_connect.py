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


def test_home_page_has_the_chats_pill_under_the_connect_pill(client):
    html = client.get("/chat").get_data(as_text=True)
    assert "keiki-strip" not in html
    stack = html.split('<div class="pill-stack">', 1)[1]
    assert stack.index("Connect your own agent") < stack.index("Put AI Partner in your chats")
    assert f"<code>Fetch {ORIGIN}/keiki.md and follow it</code>" in html
    assert f'data-copy-text="Fetch {ORIGIN}/keiki.md and follow it."' in html
    assert 'class="pill-open" data-open-dialog="keiki-dialog"' in html
    assert '<a class="keiki-badge" href="https://onkeiki.com"' in html and "Integrated with Keiki" in html
    for mark in ("imessage", "whatsapp", "slack", "telegram", "agentmail", "x", "sms", "teams"):
        assert f"/img/marks/channels/{mark}.svg" in html
        assert client.get(f"/img/marks/channels/{mark}.svg").status_code == 200
    assert client.get("/img/marks/keiki.svg").status_code == 200
    assert 'href="sms:+17796251378?&amp;body=K-XSWGQX"' in html and "Text AI Partner on iMessage" in html
    assert 'data-copy-text="K-XSWGQX"' in html and 'data-copy-text="+17796251378"' in html and "+1 (779) 625-1378" in html
    assert 'href="mailto:keiki-2w002869@agentmail.to"' in html and "Email AI Partner" in html
    assert '<dialog class="keiki-dialog" id="keiki-dialog"' in html
    assert "{{secret.AI_PARTNER_API_KEY}}" in html and f"{ORIGIN}/mcp" in html
    assert "Coming soon" in html and "/keiki.js" in html
    assert client.get("/keiki.js").status_code == 200


def _live(html):
    return [item.split("/img/marks/channels/", 1)[1].split(".svg", 1)[0] for item in html.split("<li>") if 'class="live-tag"' in item]


def test_no_channel_is_called_live_unless_listed(client, monkeypatch):
    monkeypatch.delenv("KEIKI_LIVE_CHANNELS", raising=False)
    assert _live(client.get("/chat").get_data(as_text=True)) == ["imessage", "agentmail"]
    monkeypatch.setenv("KEIKI_LIVE_CHANNELS", "")
    assert "live-tag" not in client.get("/chat").get_data(as_text=True)
    monkeypatch.setenv("KEIKI_LIVE_CHANNELS", " Telegram, bogus ")
    html = client.get("/chat").get_data(as_text=True)
    assert html.count('class="live-tag"') == 1
    live_item = html.split('class="live-tag"')[0].rsplit("<li>", 1)[1]
    assert live_item.startswith('<img src="/img/marks/channels/telegram.svg"')


def test_keiki_is_credited_in_the_footer_and_on_connect(client):
    assert 'href="https://onkeiki.com"' in client.get("/catalog").get_data(as_text=True).split('<footer class="site-foot">', 1)[1]
    connect = client.get("/connect").get_data(as_text=True)
    assert 'href="https://onkeiki.com" target="_blank" rel="noopener noreferrer">Keiki</a>' in connect
    assert "Partners:" not in connect


def test_built_on_credits_in_the_footer_and_on_connect(client):
    links = (
        "https://maritime.sh",
        "https://supermemory.ai",
        "https://onkeiki.com",
        "https://venice.ai",
        "https://exa.ai",
        "https://railway.com",
    )
    chat = client.get("/chat").get_data(as_text=True)
    footer = chat.split('<p class="built-on">', 1)[1].split("</p>", 1)[0]
    assert footer.startswith('<span class="built-on-item">Built on ')
    for name in ("Maritime", "Supermemory", "Keiki", "Venice", "Exa"):
        assert f"{name}</a> ·</span>" in footer
    assert "Railway</a></span>" in footer
    connect = client.get("/connect").get_data(as_text=True)
    section = connect.split('class="built-on-section"', 1)[1].split("</section>", 1)[0]
    for href in links:
        for block in (footer, section):
            tag = block.split(f'href="{href}"', 1)[1].split(">", 1)[0]
            assert 'target="_blank"' in tag
            assert 'rel="noopener noreferrer"' in tag


def test_keiki_md_is_an_agent_playbook(client):
    response = client.get("/keiki.md")
    assert response.status_code == 200 and response.mimetype == "text/markdown"
    text = response.get_data(as_text=True)
    assert "HOST" not in text and "DEPLOYMENT" not in text
    assert f'curl -sS -X POST "{ORIGIN}/api/signup"' in text and "USER_EMAIL" in text
    assert "`K-XSWGQX` to +1 (779) 625-1378, or email keiki-2w002869@agentmail.to" in text
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
    assert not error and started["job_id"].startswith("job_") and started["state"]["phase"] == "ask_followup"
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

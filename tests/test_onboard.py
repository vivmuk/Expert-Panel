import io
import zipfile

import pytest


def test_get_started_uses_the_request_host(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    from server import create_app

    client = create_app().test_client()
    page = client.get("/get-started.md", base_url="https://ai-partner.up.railway.app")
    assert page.status_code == 200
    assert page.mimetype == "text/markdown"
    text = page.get_data(as_text=True)
    assert "https://ai-partner.up.railway.app/signup" in text
    assert "https://ai-partner.up.railway.app/mcp" in text
    assert "https://HOST" not in text
    assert "The key is not a client id." in text
    assert "does not isolate one caller's engagements" in text
    assert "claude mcp add --transport http ai-partner --scope user" in text
    assert "list_artifacts" in text and "start_job" in text
    assert "### Grok Bot" in text
    assert "Ask Grok Bot: list the AI Partner tools." in text
    assert text.rfind("### Grok Bot") > text.rfind("### OpenCode")
    llms = client.get("/llms.txt", base_url="https://ai-partner.up.railway.app")
    assert llms.status_code == 200
    body = llms.get_data(as_text=True)
    assert "https://ai-partner.up.railway.app/get-started.md" in body
    assert "https://ai-partner.up.railway.app/openapi.json" in body
    assert "https://ai-partner.up.railway.app/mcp" in body
    assert "Grok Bot" in body
    pack = client.get("/skills.zip")
    archive = zipfile.ZipFile(io.BytesIO(pack.data))
    assert "run-engagement/SKILL.md" in archive.namelist()
    assert "read-top5/SKILL.md" in archive.namelist()
    assert "build-harness/SKILL.md" in archive.namelist()


def test_signup_issues_a_key_and_reissue_hides_the_old_one(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("AI_PARTNER_SIGNING_SECRET", "test-signing-secret")
    from server import create_app
    from server.keys import verify_key

    client = create_app().test_client()
    first = client.post("/api/signup", json={"email": "Ada@Example.com", "plan": "starter"})
    assert first.status_code == 200
    key = first.get_json()["key"]
    assert key.startswith("ap_")
    assert verify_key(key)["email"] == "ada@example.com"
    assert verify_key(key)["plan"] == "starter"
    second = client.post("/api/signup", json={"email": "ada@example.com"})
    assert second.status_code == 200
    again = second.get_json()["key"]
    assert again.startswith("ap_")
    assert again != key
    assert key not in second.get_data(as_text=True)
    assert verify_key(again)["email"] == "ada@example.com"
    landing = client.get("/chat").get_data(as_text=True)
    assert 'id="onboard-slot"' in landing
    assert "/onboard.js" in landing
    assert "Connect your own agent" in landing
    assert "/get-started.md and follow it" in landing
    assert landing.index("/img/marks/muse.svg") > landing.index("/img/marks/opencode.png")
    assert "Grok Bot" in landing
    assert landing.index('class="grok-chip"') > landing.index("/img/marks/muse.svg")
    assert "data-copy-text" in client.get("/onboard.js").get_data(as_text=True)


def test_signup_key_can_list_artifacts_over_mcp(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("AI_PARTNER_SIGNING_SECRET", "test-signing-secret")
    from server import create_app

    client = create_app().test_client()
    issued = client.post("/api/signup", json={"email": "agent@example.com", "plan": "starter"})
    key = issued.get_json()["key"]
    headers = {"Authorization": "Bearer " + key}
    opened = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "claude-code", "version": "0"}},
        },
        headers=headers,
    )
    assert opened.status_code == 200
    session = opened.headers["Mcp-Session-Id"]
    listed = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_artifacts", "arguments": {}},
        },
        headers={**headers, "Mcp-Session-Id": session},
    )
    assert listed.status_code == 200
    payload = listed.get_json()["result"]
    assert payload["isError"] is False
    assert "Data gathering" in payload["content"][0]["text"]

import hashlib
import json
import os

from server.catalog import by_id
from server.config import Config
from server.artifact_doc import as_html

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "live_engagement.json")
KEY = "partner-test-key"
HOST = "https://ai-partner.up.railway.app"
FILES = (
    "report.md",
    "deck.pptx",
    "kit.zip",
    "skill-pack.zip",
    "deck",
    "exec-memo",
    "work-chart",
    "research-brief",
    "roadmap",
)


def _state():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def _client(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", KEY)
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "ai-partner.up.railway.app")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))

    def complete(name, messages, schema, max_tokens):
        calls.append(name)
        raise AssertionError(name)

    monkeypatch.setattr("server.api.agents.complete_with_venice", complete)
    monkeypatch.setattr("server.api.chat.complete_with_venice", complete)
    monkeypatch.setattr("server.api.agents.exa_search", lambda *args, **kwargs: calls.append("exa") or [])
    from server import create_app

    return create_app().test_client()


def _owner():
    return hashlib.sha256(KEY.encode()).hexdigest()


def _save_job(state):
    from server import mcpjobs

    job_id = mcpjobs.new_id()
    mcpjobs.save(_owner(), job_id, state)
    return job_id


def _call(client, name, arguments, key=KEY):
    headers = {}
    if key is not None:
        headers["Authorization"] = "Bearer " + key
    return client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def _ok(response):
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["isError"] is False
    return json.loads(result["content"][0]["text"])


def _path(url):
    return "/r/" + url.split("/r/", 1)[1]


def _token_files(tmp_path):
    folder = tmp_path / "results"
    if not folder.exists():
        return []
    return [path for path in folder.glob("*.json")]


def test_get_report_is_stable_and_serves_the_files(monkeypatch, tmp_path):
    calls = []
    client = _client(monkeypatch, tmp_path, calls)
    state = _state()
    job_id = _save_job(state)
    first = _ok(_call(client, "get_report", {"job_id": job_id}))
    second = _ok(_call(client, "get_report", {"job_id": job_id}))
    assert first["url"] == second["url"]
    assert first["url"].startswith(HOST + "/r/")
    assert list(first["files"]) == list(FILES)
    assert set(second["files"].values()) == set(first["files"].values())
    assert len(_token_files(tmp_path)) == 1
    assert calls == []
    page = client.get(_path(first["url"]))
    assert page.status_code == 200
    assert state["problem"] in page.get_data(as_text=True)
    for name, link in first["files"].items():
        fetched = client.get(_path(link))
        assert fetched.status_code == 200, name
        if name == "report.md":
            assert state["problem"] in fetched.get_data(as_text=True)
        elif name == "deck.pptx":
            assert fetched.mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif name.endswith(".zip"):
            assert fetched.mimetype == "application/zip"
        else:
            assert "html" in fetched.mimetype
            assert "<!DOCTYPE html>" in fetched.get_data(as_text=True)


def test_get_report_requires_the_partner_key(monkeypatch, tmp_path):
    calls = []
    client = _client(monkeypatch, tmp_path, calls)
    job_id = _save_job(_state())
    missing = _call(client, "get_report", {"job_id": job_id}, key=None)
    assert missing.status_code == 401
    assert missing.get_json()["error"]["message"] == "invalid or missing API key"
    wrong = _call(client, "get_report", {"job_id": job_id}, key="not-the-key")
    assert wrong.status_code == 401
    assert calls == []
    assert _token_files(tmp_path) == []


def test_get_report_refuses_an_unfinished_job(monkeypatch, tmp_path):
    calls = []
    client = _client(monkeypatch, tmp_path, calls)
    job_id = _save_job({"chat_id": "still-asking", "phase": "ask_problem", "problem": "Not done yet."})
    response = _call(client, "get_report", {"job_id": job_id})
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["isError"] is True
    assert "not finished" in result["content"][0]["text"]
    assert calls == []
    assert _token_files(tmp_path) == []


def test_share_reuses_the_same_link_as_get_report(monkeypatch, tmp_path):
    calls = []
    client = _client(monkeypatch, tmp_path, calls)
    state = _state()
    job_id = _save_job(state)
    report = _ok(_call(client, "get_report", {"job_id": job_id}))
    first = client.post("/api/chat/share", json={"state": state})
    changed = dict(state, problem=state["problem"] + " Updated line.")
    second = client.post("/api/chat/share", json={"state": changed})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["url"] == report["url"]
    assert second.get_json()["url"] == report["url"]
    page = client.get(_path(report["url"]))
    assert "Updated line." in page.get_data(as_text=True)
    early = client.post("/api/chat/share", json={"state": {"phase": "ask_problem", "chat_id": state["chat_id"], "problem": "no"}})
    assert early.status_code == 400
    assert early.get_json()["error"]["code"] == "not_ready"
    bare = dict(state)
    bare.pop("chat_id")
    assert client.post("/api/chat/share", json={"state": bare}).status_code == 400
    assert len(_token_files(tmp_path)) == 1
    assert calls == []


def test_chat_turn_includes_the_link_the_first_time_the_job_is_done(monkeypatch, tmp_path):
    calls = []
    client = _client(monkeypatch, tmp_path, calls)

    def complete(name, messages, schema, max_tokens):
        calls.append(name)
        return {"skills": [{"name": "run-the-engagement", "description": "Use when the engagement is ready.", "tools": ["read"]}]}

    monkeypatch.setattr("server.api.agents.complete_with_venice", complete)
    state = _state()
    state.pop("pack", None)
    state.pop("sig", None)
    state["calls"] = 0
    state["phase"] = "skills"
    job_id = _save_job(state)
    finished = _ok(_call(client, "chat_turn", {"job_id": job_id, "message": ""}))
    assert calls == ["ChatSkills"]
    assert finished["url"].startswith(HOST + "/r/")
    again = _ok(_call(client, "chat_turn", {"job_id": job_id, "message": "thanks"}))
    assert "url" not in again
    report = _ok(_call(client, "get_report", {"job_id": job_id}))
    assert report["url"] == finished["url"]
    page = client.get(_path(finished["url"]))
    assert page.status_code == 200
    assert state["problem"] in page.get_data(as_text=True)
    shared = client.post("/api/chat/share", json={"state": _state()})
    assert shared.status_code == 200
    assert shared.get_json()["url"] == finished["url"]
    assert calls == ["ChatSkills"]


def test_generate_artifact_includes_html(monkeypatch, tmp_path):
    from tests.test_catalog import _state as catalog_state

    calls = []
    client = _client(monkeypatch, tmp_path, calls)

    def complete(name, messages, schema, max_tokens):
        calls.append(name)
        return {"markdown": "## Purpose\n\nRun the count.\n"}

    monkeypatch.setattr("server.api.agents.complete_with_venice", complete)
    payload = _ok(_call(client, "generate_artifact", {"artifact_id": "charter", "state": catalog_state()}))
    assert calls == ["ChatArtifact"]
    assert "Run the count." in payload["html"]
    assert payload["html"] == as_html(by_id("charter")["title"], payload["markdown"])


def test_finished_chat_offers_copy_link():
    from server import create_app

    script = create_app().test_client().get("/chat.js").get_data(as_text=True)
    assert 's.phase === "done"' in script
    assert "Copy link" in script
    assert "/api/chat/share" in script

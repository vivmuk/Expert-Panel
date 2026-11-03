"""Visitor memory stays per browser, and a first visit does not search."""
import logging
import threading
from pathlib import Path

import pytest
import requests
from werkzeug.serving import make_server

from server.chatmemory import _scalar_metadata, memory_namespace, recall, remember, reset_written
from tests.test_chatjob import ONE_SHOT, fake_model

# chatmemory tests replace requests.post. Keep the original for the live server.
_real_post = requests.post
_CHAT_JS = Path(__file__).resolve().parents[1] / "server" / "static" / "chat.js"

OTHER = "Pricing for a B2B analytics product. Team: 3 managers. Tools: Excel. Maturity 2."
PHRASE = "medtech device into Germany"
WRITE_URL = "https://api.supermemory.ai/v3/documents"
WRITE_KEYS = {"content", "customId", "containerTags", "metadata"}


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class MemoryStub:
    def __init__(self):
        self.calls = []
        self.docs = []

    def post(self, url, headers, json, timeout):
        self.calls.append({"method": "POST", "url": url, "json": json, "headers": headers, "timeout": timeout})
        if url == WRITE_URL:
            tags = json.get("containerTags")
            if not isinstance(tags, list) or len(tags) != 1 or not isinstance(tags[0], str):
                raise AssertionError(json)
            self.docs.append({"ns": tags[0], "body": json})
            return _Response({})
        if url.endswith("/search"):
            ns = _ns(url)
            hits = [{"memory": doc["body"]["content"]} for doc in self.docs if doc["ns"] == ns]
            return _Response({"results": hits})
        raise AssertionError(url)

    def searches(self):
        return [call for call in self.calls if call["url"].endswith("/search")]


def _ns(url):
    return url.split("/ns/")[1].split("/")[0]


def _install(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "test-memory-key")
    stub = MemoryStub()
    monkeypatch.setattr("server.chatmemory.requests.post", stub.post)
    return stub


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AI_PARTNER_DAILY_ENGAGEMENTS", "50")
    _install(monkeypatch)
    monkeypatch.setattr("server.api.chat.complete_with_venice", fake_model([]))
    monkeypatch.setattr("server.api.chat.exa_search", lambda query, limit=4: [])
    from server import create_app

    return create_app().test_client()


def _turn(post, message, visitor_id, has_history=False, state=None):
    res = post({
        "message": message,
        "state": state or {},
        "visitor_id": visitor_id,
        "has_history": has_history,
    })
    assert res.status_code == 200, res.text[:400]
    body = res.json() if hasattr(res, "json") and not hasattr(res, "get_json") else res.get_json()
    assert not body.get("error"), body.get("error")
    return body


def _flask_post(client):
    def post(payload):
        return client.post("/api/chat", json=payload)

    return post


def _drive(post, message, visitor_id, has_history=False):
    body = _turn(post, message, visitor_id, has_history)
    for _ in range(16):
        if (body.get("card") or {}).get("kind") == "top5":
            return body
        if not body.get("next"):
            return body
        body = _turn(post, "", visitor_id, has_history, body["state"])
    raise AssertionError(body["state"]["phase"])


def test_chat_page_script_persists_a_visitor_and_sends_it():
    text = _CHAT_JS.read_text(encoding="utf-8")
    assert "ai-partner-visitor" in text
    assert "ai-partner-has-history" in text
    assert "crypto.randomUUID" in text
    assert "visitor_id: visitorId()" in text
    assert "has_history: hasHistory()" in text
    assert "localStorage.setItem(HISTORY_KEY" in text


def test_same_visitor_recalls_across_chats_and_a_new_visitor_does_not_search(client, monkeypatch):
    stub = _install(monkeypatch)
    post = _flask_post(client)
    first = _drive(post, ONE_SHOT, "alpha")
    assert first["card"]["kind"] == "top5"
    assert stub.searches() == []
    assert len(stub.docs) == 1
    chat_id = first["state"]["chat_id"]
    doc = stub.docs[0]
    assert doc["ns"] == "visitor-alpha"
    assert set(doc["body"]) == WRITE_KEYS
    assert doc["body"]["containerTags"] == ["visitor-alpha"]
    assert doc["body"]["customId"] == "visitor-alpha-" + chat_id
    assert PHRASE in doc["body"]["content"]

    second = _turn(post, OTHER, "alpha", has_history=False)
    assert second["state"]["chat_id"] != chat_id
    assert [call["url"] for call in stub.searches()] == ["https://api.supermemory.ai/ns/visitor-alpha/search"]
    assert PHRASE in second["state"]["memories"]
    assert "B2B analytics" not in second["state"]["memories"]

    reset_written()
    held = len(stub.searches())
    quiet = _turn(post, OTHER, "alpha", has_history=False)
    assert len(stub.searches()) == held
    assert quiet["state"]["memories"] == ""
    again = _turn(post, OTHER, "alpha", has_history=True)
    assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/visitor-alpha/search"
    assert PHRASE in again["state"]["memories"]

    before = len(stub.searches())
    fresh = _turn(post, OTHER, "gamma", has_history=False)
    assert len(stub.searches()) == before
    assert fresh["state"]["memories"] == ""
    assert all("visitor-gamma" not in call["url"] for call in stub.calls)


def test_two_visitors_are_isolated(client, monkeypatch):
    stub = _install(monkeypatch)
    post = _flask_post(client)
    _drive(post, ONE_SHOT, "alpha")
    beta = _turn(post, OTHER, "beta", has_history=True)
    assert beta["state"]["memories"] == ""
    assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/visitor-beta/search"
    assert PHRASE not in beta["state"]["memories"]
    alpha = _turn(post, OTHER, "alpha", has_history=True)
    assert PHRASE in alpha["state"]["memories"]
    assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/visitor-alpha/search"
    assert "visitor-beta" not in alpha["state"]["memories"]


def test_first_turn_makes_no_search_request(client, monkeypatch):
    stub = _install(monkeypatch)
    res = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}, "visitor_id": "alpha", "has_history": False})
    assert res.status_code == 200
    assert stub.searches() == []
    assert stub.calls == []


def test_engagements_accumulate_for_one_visitor(monkeypatch):
    stub = _install(monkeypatch)
    remember("chatA", "Problem: alpha widgets", visitor_id="alpha")
    remember("chatB", "Problem: alpha follow-up", visitor_id="alpha")
    remember("chatC", "Problem: beta only", visitor_id="beta")
    assert [doc["body"]["customId"] for doc in stub.docs] == [
        "visitor-alpha-chatA",
        "visitor-alpha-chatB",
        "visitor-beta-chatC",
    ]
    assert [doc["body"]["containerTags"] for doc in stub.docs] == [
        ["visitor-alpha"],
        ["visitor-alpha"],
        ["visitor-beta"],
    ]
    assert len({doc["body"]["customId"] for doc in stub.docs if doc["ns"] == "visitor-alpha"}) == 2
    for doc in stub.docs:
        assert set(doc["body"]) == WRITE_KEYS
        assert doc["body"]["containerTags"] == [doc["ns"]]
    alpha = recall("chatD", "widgets", visitor_id="alpha")
    assert "alpha widgets" in alpha and "alpha follow-up" in alpha
    assert "beta only" not in alpha
    beta = recall("chatE", "widgets", visitor_id="beta", has_history=True)
    assert beta == "Problem: beta only"
    assert "alpha" not in beta


def test_malformed_visitor_id_is_sanitized_or_ignored(monkeypatch):
    stub = _install(monkeypatch)
    assert memory_namespace("chat1", "../") == "chat-chat1"
    assert memory_namespace("chat1", "..") == "chat-chat1"
    assert memory_namespace("chat1", "///") == "chat-chat1"
    assert memory_namespace("chat1", "你好") == "chat-chat1"
    assert memory_namespace("chat1", "../../etc/passwd") == "visitor-etcpasswd"
    assert memory_namespace("chat1", "../abc") == "visitor-abc"
    assert memory_namespace("chat1", "a" * 500) == "visitor-" + ("a" * 40)
    assert memory_namespace("chat1", "café-用户-2") == "visitor-caf--2"
    assert ".." not in memory_namespace("chat1", "../etc/passwd")

    remember("chat1", "hello", visitor_id="../../etc/passwd")
    assert stub.calls[-1]["url"] == WRITE_URL
    assert ".." not in stub.calls[-1]["url"]
    assert stub.calls[-1]["json"]["customId"] == "visitor-etcpasswd-chat1"
    assert stub.calls[-1]["json"]["containerTags"] == ["visitor-etcpasswd"]
    assert ".." not in stub.calls[-1]["json"]["customId"]
    assert ".." not in stub.calls[-1]["json"]["containerTags"][0]

    before = len(stub.calls)
    assert recall("chat1", "hello", visitor_id="../", has_history=True) == ""
    assert recall("chat1", "hello", visitor_id="你好", has_history=True) == ""
    assert len(stub.calls) == before

    recall("chat9", "query", visitor_id="b" * 200, has_history=True)
    assert stub.calls[-1]["url"] == "https://api.supermemory.ai/ns/" + "visitor-" + ("b" * 40) + "/search"
    recall("chat9", "query", visitor_id="../abc", has_history=True)
    assert stub.calls[-1]["url"] == "https://api.supermemory.ai/ns/visitor-abc/search"


def test_route_ignores_malformed_visitor_ids(client, monkeypatch):
    stub = _install(monkeypatch)
    post = _flask_post(client)
    missed = _turn(post, ONE_SHOT, "../", has_history=True)
    assert missed["state"]["memories"] == ""
    assert stub.searches() == []
    missed = _turn(post, ONE_SHOT, "你好", has_history=True)
    assert stub.searches() == []
    hit = _turn(post, ONE_SHOT, "../abc", has_history=True)
    assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/visitor-abc/search"
    assert ".." not in stub.searches()[-1]["url"]
    _turn(post, ONE_SHOT, "c" * 120, has_history=True)
    assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/" + "visitor-" + ("c" * 40) + "/search"
    assert hit["state"]["chat_id"]


def test_running_app_stubs_supermemory_for_two_chats(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AI_PARTNER_DAILY_ENGAGEMENTS", "50")
    stub = _install(monkeypatch)
    monkeypatch.setattr("server.api.chat.complete_with_venice", fake_model([]))
    monkeypatch.setattr("server.api.chat.exa_search", lambda query, limit=4: [])
    from server import create_app

    httpd = make_server("127.0.0.1", 0, create_app())
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{httpd.server_port}"

    def post(payload):
        return _real_post(origin + "/api/chat", json=payload, timeout=30)

    try:
        first = _drive(post, ONE_SHOT, "alpha")
        assert stub.searches() == []
        assert stub.docs[0]["ns"] == "visitor-alpha"
        assert PHRASE in stub.docs[0]["body"]["content"]
        second = _turn(post, OTHER, "alpha", has_history=True)
        assert second["state"]["chat_id"] != first["state"]["chat_id"]
        assert stub.searches()[-1]["url"] == "https://api.supermemory.ai/ns/visitor-alpha/search"
        assert PHRASE in second["state"]["memories"]
        before = len(stub.searches())
        fresh = _turn(post, OTHER, "gamma", has_history=False)
        assert len(stub.searches()) == before
        assert fresh["state"]["memories"] == ""
        assert all(
            call["url"] == WRITE_URL or call["url"].startswith("https://api.supermemory.ai/ns/visitor-")
            for call in stub.calls
        )
        writes = [call for call in stub.calls if call["url"] == WRITE_URL]
        assert writes
        assert all(call["json"]["containerTags"] == ["visitor-alpha"] for call in writes)
        assert all("visitor-gamma" not in call["url"] for call in stub.calls)
    finally:
        httpd.shutdown()


def _assert_write(call, ns, custom_id):
    assert call["method"] == "POST"
    assert call["url"] == WRITE_URL
    body = call["json"]
    assert set(body) == WRITE_KEYS
    assert isinstance(body["containerTags"], list)
    assert body["containerTags"] == [ns]
    assert body["customId"] == custom_id
    assert body["metadata"] == {"type": "engagement"}
    assert "containerTag" not in body
    assert "id" not in body
    for value in body["metadata"].values():
        assert isinstance(value, (str, int, float, bool))


def test_remember_posts_the_v3_document_shape(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "test-memory-key")
    seen = []

    def post(url, headers, json, timeout):
        seen.append({"method": "POST", "url": url, "json": json, "headers": headers, "timeout": timeout})
        return _Response({})

    def unexpected(*args, **kwargs):
        raise AssertionError("remember used a method other than POST")

    monkeypatch.setattr("server.chatmemory.requests.post", post)
    for name in ("get", "put", "patch", "delete", "head", "request"):
        monkeypatch.setattr("server.chatmemory.requests." + name, unexpected, raising=False)

    remember("chatA", "Problem: alpha widgets", visitor_id="alpha")
    remember("chatB", "Problem: alpha follow-up", visitor_id="alpha")
    remember("chatC", "Problem: beta only", visitor_id="beta")
    remember("abc_123", "hello")

    assert len(seen) == 4
    _assert_write(seen[0], "visitor-alpha", "visitor-alpha-chatA")
    _assert_write(seen[1], "visitor-alpha", "visitor-alpha-chatB")
    _assert_write(seen[2], "visitor-beta", "visitor-beta-chatC")
    _assert_write(seen[3], "chat-abc_123", "chat-abc_123-abc_123")
    assert seen[0]["json"]["customId"] != seen[1]["json"]["customId"]
    assert seen[0]["json"]["containerTags"] == seen[1]["json"]["containerTags"]
    assert seen[2]["json"]["containerTags"] != seen[0]["json"]["containerTags"]
    assert seen[0]["headers"]["Authorization"] == "Bearer test-memory-key"
    assert "test-memory-key" not in seen[0]["url"]

    remember("chatA", "Problem: alpha widgets", visitor_id="alpha")
    assert len(seen) == 4

    remember("chatA", "Problem: alpha widgets, revised", visitor_id="alpha")
    assert len(seen) == 5
    _assert_write(seen[4], "visitor-alpha", "visitor-alpha-chatA")
    assert seen[4]["json"]["content"] != seen[0]["json"]["content"]


def test_metadata_keeps_only_plain_scalars():
    assert _scalar_metadata(
        {
            "type": "engagement",
            "n": 1,
            "ok": True,
            "ratio": 0.5,
            "nested": {"a": 1},
            "tags": ["x"],
            "empty": None,
        }
    ) == {"type": "engagement", "n": 1, "ok": True, "ratio": 0.5}


def test_one_engagement_posts_a_single_document(client, monkeypatch):
    stub = _install(monkeypatch)
    post = _flask_post(client)
    body = _turn(post, ONE_SHOT, "alpha")
    for _ in range(20):
        if not body.get("next"):
            break
        body = _turn(post, "", "alpha", False, body["state"])
    else:
        raise AssertionError(body["state"]["phase"])
    assert body["state"]["phase"] == "ask_size"
    assert len(stub.docs) == 1
    done = _turn(post, "12 people", "alpha", False, body["state"])
    assert done["state"]["phase"] == "done"
    assert len(stub.docs) == 1
    _assert_write(
        stub.calls[0],
        "visitor-alpha",
        "visitor-alpha-" + done["state"]["chat_id"],
    )
    assert all(call["url"] == WRITE_URL for call in stub.calls)


def test_remember_logs_status_and_body_without_the_key(monkeypatch, caplog):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "test-memory-key")

    class Bad:
        status_code = 400
        text = '{"code":"unrecognized_keys","keys":["customId","containerTag"]}'

        def raise_for_status(self):
            raise requests.HTTPError("400 Client Error")

    def post(url, headers, json, timeout):
        return Bad()

    monkeypatch.setattr("server.chatmemory.requests.post", post)
    with caplog.at_level(logging.INFO, logger="server.chatmemory"):
        remember("chatA", "Problem: alpha", visitor_id="alpha")
    failed = [rec.message for rec in caplog.records if "supermemory remember failed" in rec.message]
    assert len(failed) == 1
    assert "status=400" in failed[0]
    assert "unrecognized_keys" in failed[0]
    assert "containerTag" in failed[0]
    assert "test-memory-key" not in failed[0]
    assert "Authorization" not in failed[0]
    assert "Bearer" not in failed[0]

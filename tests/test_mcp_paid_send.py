"""Authenticated MCP paid turns use the same chat send as POST /api/chat.

The provider is a local double. These tests do not call Venice.
"""
import json

from server.config import Config
from server.chatjob import handle_turn

SHOP = (
    "We run a single-location shop with 3-6 staff. "
    "The bottleneck is the morning handoff between the counter and the kitchen. "
    "The shop owner, Maya, would own the fix. "
    "We are using Square and a paper notebook."
)
AUTH = {"Authorization": "Bearer partner-test-key"}
RESEARCH = {
    "chat_id": "mcpshop00000001",
    "phase": "research",
    "problem": "A single-location shop with 3-6 staff.",
    "team": "3-6 staff",
    "tools": "Square",
    "maturity": 2,
    "size": "small",
    "calls": 0,
}


class _Response:
    def __init__(self, payload):
        self.status_code = 200
        self.headers = {}
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        return self._payload


def _provider(monkeypatch):
    calls = []

    def request(self, method, url, *args, **kwargs):
        body = kwargs.get("json") or {}
        user = ""
        for message in body.get("messages") or []:
            if isinstance(message, dict) and message.get("role") == "user":
                user = str(message.get("content") or "")
        calls.append(url)
        content = {
            "questions": ["What's the specific bottleneck, and who on the team would own the fix?"],
            "maturity": 2,
            "size": "large",
            "size_question": "Is this the whole company?",
            "team": user[:1000],
            "tools": user[:1000],
            "service_line": "retail",
            "facts": ["The client described a single-location shop."],
            "queries": ["shop benchmarks", "shop rivals", "shop rules"],
            "markdown": "A short memo for the shop.",
        }
        return _Response(
            {
                "choices": [{"message": {"content": json.dumps(content)}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "cost_usd": 0.001,
            }
        )

    monkeypatch.setattr("requests.sessions.Session.request", request)
    return calls


def _recorded(monkeypatch):
    rows = []

    def remember(source, identity, kind, ref=None, **_kwargs):
        rows.append({"source": source, "identity": identity, "kind": kind, "ref": ref})

    monkeypatch.setattr("server.accounts.remember_connection", remember)
    return rows


def _client(monkeypatch, tmp_path, railway):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    if railway:
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    else:
        from server.chat_send import RAILWAY_MARKERS

        for name in RAILWAY_MARKERS:
            monkeypatch.delenv(name, raising=False)
    from server import create_app

    return create_app().test_client()


def _tool(client, name, arguments, call_id):
    res = client.post(
        "/mcp",
        headers=AUTH,
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()["result"]
    text = body["content"][0]["text"]
    parsed = None
    if not body["isError"]:
        parsed = json.loads(text)
    return body, parsed, text


def _bad_intake(name, messages, schema, max_tokens):
    del schema, max_tokens
    user = ""
    for message in messages or []:
        if isinstance(message, dict) and message.get("role") == "user":
            user = str(message.get("content") or "")
    if name != "ChatIntake":
        return {
            "facts": ["The client stated the problem."],
            "service_line": "retail",
            "queries": ["retail benchmarks", "retail rivals", "retail rules"],
        }
    return {
        "questions": ["What's the specific bottleneck, and who on the team would own the fix?"],
        "maturity": 2,
        "size": "large",
        "size_question": "Is this the whole company?",
        "team": user[:1000],
        "tools": user[:1000],
    }


def test_shop_brief_keeps_a_short_team_and_does_not_reask():
    opened = handle_turn({}, SHOP, _bad_intake)
    assert opened["state"]["size"] == "small"
    assert opened["state"]["team"] == "3-6 staff"
    assert "Square" in opened["state"]["tools"]
    assert "bottleneck" not in opened["reply"].lower()
    assert "own" not in opened["reply"].lower()
    assert opened["state"]["phase"] == "ask_followup"


def test_single_location_shop_is_small_even_when_the_model_says_large():
    brief = "A single-location shop. The bottleneck is the morning handoff. The owner Maya would own the fix."
    opened = handle_turn({}, brief, _bad_intake)
    assert opened["state"]["size"] == "small"
    assert opened["state"]["team"] == ""
    assert "bottleneck" not in opened["reply"].lower()


def test_ambiguous_size_is_asked_instead_of_assumed_large():
    opened = handle_turn({}, "We should improve how the shop runs.", _bad_intake)
    assert "bottleneck" in opened["reply"].lower()
    answered = handle_turn(
        opened["state"],
        "The close is the bottleneck and the owner handles it.",
        _bad_intake,
    )
    assert answered["state"]["size"] == ""
    assert answered["state"]["phase"] == "ask_size"
    assert answered["state"]["team"] == ""


def test_authenticated_mcp_paid_turn_uses_the_configured_send(monkeypatch, tmp_path):
    calls = _provider(monkeypatch)
    recorded = _recorded(monkeypatch)
    client = _client(monkeypatch, tmp_path, railway=True)
    denied = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "start_job", "arguments": {"message": SHOP}}},
    )
    assert denied.status_code == 401
    assert calls == []

    _body, started, _text = _tool(client, "start_job", {"message": SHOP}, 2)
    assert calls
    assert all(url.endswith("/chat/completions") for url in calls)
    assert started["state"]["size"] == "small"
    assert started["state"]["team"] == "3-6 staff"
    assert "Square" in started["state"]["tools"]
    assert "bottleneck" not in started["reply"].lower()
    assert (started.get("error") or {}).get("code") != "currency_bound_unavailable"
    held = len(calls)

    _body, artifact, text = _tool(
        client,
        "generate_artifact",
        {"job_id": started["job_id"], "artifact_id": "research-brief"},
        3,
    )
    assert len(calls) > held
    assert "Paid work is stopped" not in text
    assert "memo" in artifact["markdown"].lower()
    held = len(calls)

    _body, turned, text = _tool(
        client,
        "chat_turn",
        {"job_id": started["job_id"], "message": "We tried a paper checklist last month."},
        4,
    )
    assert len(calls) > held
    assert "Paid work is stopped" not in text
    assert (turned.get("error") or {}).get("code") != "currency_bound_unavailable"
    assert turned.get("next")
    held = len(calls)
    paid = client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"model": "ai-partner", "messages": [{"role": "user", "content": "Pricing for a B2B analytics product"}]},
    )
    assert paid.status_code == 200, paid.get_data(as_text=True)
    assert "Paid work is stopped" not in paid.get_json()["choices"][0]["message"]["content"]
    assert len(calls) > held
    identities = {row["identity"] for row in recorded if row["source"] == "agent"}
    assert identities
    assert "partner-test-key" not in identities
    assert any(row["kind"] in ("question", "run") for row in recorded if row["source"] == "agent")


def test_mcp_paid_tools_stay_closed_off_railway(monkeypatch, tmp_path):
    calls = _provider(monkeypatch)
    client = _client(monkeypatch, tmp_path, railway=False)
    _body, turned, text = _tool(client, "chat_turn", {"message": "Continue.", "state": RESEARCH}, 1)
    assert calls == []
    assert turned["error"]["code"] == "currency_bound_unavailable"
    assert "configured chat send" in text
    _body, _parsed, text = _tool(
        client,
        "generate_artifact",
        {"artifact_id": "research-brief", "state": RESEARCH},
        2,
    )
    assert calls == []
    assert "configured chat send" in text

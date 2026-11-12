"""No-network characterization of Keiki intake routing.

Arbitrary prose such as "do not run the panel" is not a control contract. Once
the message also contains a team, tools, and a maturity score, the engine
starts research and the push loop keeps going while `next` is set. An echo
token in that prose is not copied into the reply.
"""
import json

from tests.test_chatjob import fake_model

STOP = "Do not run the panel. Echo token ECHO-7. Ask only the first intake question."
STARTS_WORK = (
    "Do not run the panel. Echo token ECHO-7. "
    "Market entry for a medtech device into Germany. "
    "Team: 4 analysts. Tools: Excel and Veeva. Maturity 2."
)
AUTH = {"Authorization": "Bearer partner-test-key"}


def _doubles(monkeypatch):
    calls = []
    searches = []
    monkeypatch.setattr("server.api.agents.complete_with_venice", fake_model(calls))
    monkeypatch.setattr("server.api.agents.exa_search", lambda query, limit=4: searches.append(query) or [])
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    return calls, searches


def _mcp(monkeypatch, tmp_path):
    from server.config import Config
    from server import create_app

    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    return create_app().test_client()


def _tool(client, name, arguments, call_id):
    res = client.post(
        "/mcp",
        headers=AUTH,
        json={"jsonrpc": "2.0", "id": call_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    return json.loads(res.get_json()["result"]["content"][0]["text"])


def test_mcp_stop_prose_without_intake_does_not_call_the_model(monkeypatch, tmp_path):
    calls, searches = _doubles(monkeypatch)
    client = _mcp(monkeypatch, tmp_path)
    result = _tool(client, "start_job", {"message": STOP}, 1)
    assert result["state"]["phase"] == "ask_followup"
    assert "Invoice-led" not in result["reply"]
    assert result["next"] is None
    assert "ECHO-7" not in result["reply"]
    assert calls == ["ChatIntake"]
    assert searches == []


def test_mcp_stop_prose_with_intake_starts_research(monkeypatch, tmp_path):
    """Current behavior, not a desired contract. The stop sentence does not hold the run."""
    calls, searches = _doubles(monkeypatch)
    client = _mcp(monkeypatch, tmp_path)
    result = _tool(client, "start_job", {"message": STARTS_WORK}, 1)
    assert result["state"]["phase"] == "ask_followup"
    assert calls == ["ChatIntake"]
    result = _tool(client, "chat_turn", {"job_id": result["job_id"], "message": "The commercial lead owns the bottleneck."}, 2)
    assert result["next"] == "synthesize"
    assert calls[0] == "ChatIntake"
    assert "ChatResearch" in calls
    assert searches
    guard = 0
    while result.get("next"):
        guard += 1
        assert guard < 20
        result = _tool(client, "chat_turn", {"job_id": result["job_id"], "message": ""}, guard + 1)
    assert "ChatChart" in calls
    assert calls[0] == "ChatIntake"
    assert "ECHO-7" not in json.dumps(result)


def test_run_turn_loop_is_not_signed_http_or_channel_delivery(monkeypatch, tmp_path):
    """Calls run_turn directly. It does not check Keiki-Signature and it does not deliver email or iMessage."""
    from server.api import keiki

    calls, searches = _doubles(monkeypatch)
    _mcp(monkeypatch, tmp_path)
    posted = []
    monkeypatch.setattr(keiki, "_post", lambda url, token, body: posted.append(body))
    keiki._states.clear()
    keiki.run_turn(
        {
            "type": "keiki.turn",
            "turnId": "stop-1",
            "agentId": "agent-1",
            "conversationId": "stop-1",
            "messages": [{"text": STOP}],
            "keiki": {"turnUrl": "https://keiki.example/turns/stop-1"},
        },
        "turn-token",
    )
    texts = [item.get("text") for item in posted if "text" in item]
    assert texts and "about 4 minutes" not in texts[0]
    assert "Invoice-led" not in texts[0]
    assert posted[-1] == {"status": "completed"}
    assert calls == ["ChatIntake"]
    assert searches == []
    assert "ECHO-7" not in json.dumps(posted)

    posted.clear()
    calls.clear()
    searches.clear()
    keiki.run_turn(
        {
            "type": "keiki.turn",
            "turnId": "work-1",
            "agentId": "agent-1",
            "conversationId": "clinic",
            "messages": [{"text": STARTS_WORK}],
            "keiki": {"turnUrl": "https://keiki.example/turns/work-1"},
        },
        "turn-token",
    )
    assert calls == ["ChatIntake"]
    keiki.run_turn(
        {
            "type": "keiki.turn",
            "turnId": "work-2",
            "agentId": "agent-1",
            "conversationId": "clinic",
            "messages": [{"text": "The commercial lead owns the bottleneck."}],
            "keiki": {"turnUrl": "https://keiki.example/turns/work-2"},
        },
        "turn-token",
    )
    assert calls[0] == "ChatIntake"
    assert "ChatResearch" in calls
    assert "ChatChart" in calls
    assert searches
    assert posted[-1] == {"status": "completed"}
    assert "ECHO-7" not in json.dumps(posted)


def test_signed_http_turn_reaches_the_same_router(monkeypatch, tmp_path):
    """Signed POST /keiki/turn with a local double. This is ingress validation, not a Keiki or email delivery."""
    import json as jsonlib

    from server.api import keiki
    from tests.test_keiki import SECRET, _sign

    calls, searches = _doubles(monkeypatch)
    monkeypatch.setenv("KEIKI_HARNESS_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("KEIKI_AGENT_ID", "agent-1")
    client = _mcp(monkeypatch, tmp_path)
    posted = []
    monkeypatch.setattr(keiki, "_post", lambda url, token, body: posted.append(body))

    real_thread = keiki.threading.Thread

    def thread_factory(*args, **kwargs):
        target = kwargs.get("target")
        if target is keiki.run_turn:
            class _Inline:
                def start(self):
                    target(*kwargs["args"])

            return _Inline()
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(keiki.threading, "Thread", thread_factory)
    keiki.reset_replays()
    keiki._states.clear()

    def post(turn_id, text, conversation):
        raw = jsonlib.dumps(
            {
                "type": "keiki.turn",
                "turnId": turn_id,
                "agentId": "agent-1",
                "conversationId": conversation,
                "messages": [{"text": text}],
                "keiki": {"turnUrl": f"https://keiki.example/turns/{turn_id}"},
            }
        ).encode()
        return client.post(
            "/keiki/turn",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "Keiki-Signature": _sign(raw),
                "Keiki-Turn-Token": "turn-token",
            },
        )

    stopped = post("http-stop", STOP, "stop-clinic")
    assert stopped.status_code == 202
    texts = [item.get("text") for item in posted if "text" in item]
    assert texts and "about 4 minutes" not in texts[0]
    assert "Invoice-led" not in texts[0]
    assert posted[-1] == {"status": "completed"}
    assert calls == ["ChatIntake"]
    assert searches == []
    posted.clear()
    calls.clear()
    worked = post("http-work", STARTS_WORK, "work-clinic")
    assert worked.status_code == 202
    assert calls == ["ChatIntake"]
    posted.clear()
    continued = post("http-work-2", "The commercial lead owns the bottleneck.", "work-clinic")
    assert continued.status_code == 202
    assert calls[0] == "ChatIntake"
    assert "ChatResearch" in calls
    assert searches
    assert posted[-1] == {"status": "completed"}
    assert "ECHO-7" not in json.dumps(posted)

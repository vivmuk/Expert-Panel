import pytest

from server.api.chat import reset_limits
from server.budget import reset as reset_budget
from server.venice.errors import VeniceError

ONE_SHOT = (
    "Market entry for a medtech device into Germany. "
    "Team: 4 analysts. Tools: Excel and Veeva. Maturity 2."
)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    reset_limits()
    reset_budget()
    from server import create_app

    return create_app()


def _raise(exc):
    def complete(name, messages, schema, max_tokens):
        raise exc

    return complete


RESEARCH = {
    "chat_id": "errchat00000001",
    "phase": "research",
    "problem": "Market entry for a medtech device into Germany.",
    "team": "4 analysts",
    "tools": "Excel and Veeva",
    "maturity": 2,
    "size": "small",
    "calls": 0,
}


def test_spend_limit_returns_503_and_keeps_the_answers(app, monkeypatch):
    error = VeniceError("HTTP 402 from /chat/completions: insufficient balance", 402, "{}")
    monkeypatch.setattr("server.api.chat.complete_with_venice", _raise(error))
    res = app.test_client().post("/api/chat", json={"message": "", "state": RESEARCH})
    assert res.status_code == 503
    data = res.get_json()
    assert data["error"]["code"] == "spend_limit"
    assert "spending limit" in data["reply"]
    assert "answers are saved" in data["reply"]
    assert data["state"]["problem"].startswith("Market entry")
    assert data["next"] is None


def test_intake_call_failure_asks_a_generic_question(app, monkeypatch):
    monkeypatch.setattr("server.api.chat.complete_with_venice", _raise(VeniceError("HTTP 402", 402)))
    res = app.test_client().post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert res.status_code == 200
    data = res.get_json()
    assert data["state"]["phase"] == "ask_followup"
    assert "Invoice-led" not in data["reply"]
    assert data.get("error") is None


def test_spend_limit_is_found_through_a_wrapped_error(app, monkeypatch):
    def complete(name, messages, schema, max_tokens):
        try:
            raise VeniceError("HTTP 402", 402)
        except VeniceError as exc:
            raise RuntimeError("structured call failed") from exc

    monkeypatch.setattr("server.api.chat.complete_with_venice", complete)
    res = app.test_client().post("/api/chat", json={"message": "", "state": RESEARCH})
    assert res.status_code == 503


def test_other_model_errors_return_502(app, monkeypatch):
    monkeypatch.setattr("server.api.chat.complete_with_venice", _raise(VeniceError("HTTP 400", 400)))
    res = app.test_client().post("/api/chat", json={"message": "", "state": RESEARCH})
    assert res.status_code == 502
    data = res.get_json()
    assert data["error"]["code"] == "model"
    assert data["state"]["problem"].startswith("Market entry")


def test_stateless_chat_and_artifact_map_spend_limit_to_503(app, monkeypatch):
    monkeypatch.setattr("server.api.chat.complete_with_venice", _raise(VeniceError("HTTP 402", 402)))
    http = app.test_client()
    assert http.post("/chat", json={"message": "Market entry into Germany"}).status_code == 503
    res = http.post("/api/chat/artifact", json={"artifact_id": "exec-memo", "state": {"problem": "x", "maturity": 2}})
    assert res.status_code in (400, 503)

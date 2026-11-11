"""Email sign-in, the three-question quota, and the Railway/Maritime split.

Uses the disposable local Postgres from EXPOSURE_TEST_DATABASE_URL. It does
not call a provider. A question is one signed-in prompt that would call a
provider. Intake does not count.
"""
import re
import secrets
from urllib.parse import parse_qs, urlparse

import pytest

from server.accounts import drop_test_schema, install_test_schema, set_run_costs, usage_report
from server.mailer import CaptureMailer, install, reset
from tests.test_chatjob import ONE_SHOT
from tests.test_pg_authority import resolve_test_dsn


def _token(message):
    match = re.search(r"https?://\S+", message["text"])
    return parse_qs(urlparse(match.group(0)).query)["token"][0]


@pytest.fixture
def world(monkeypatch):
    dsn = resolve_test_dsn()
    schema = "acct_" + secrets.token_hex(8)
    install_test_schema(dsn, schema)
    monkeypatch.setenv("AI_PARTNER_ACCOUNT_ROLE", "authority")
    monkeypatch.setenv("AI_PARTNER_ACCOUNTS_TEST", "1")
    monkeypatch.setenv("AI_PARTNER_ACCOUNTS_SCHEMA", schema)
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "test")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    box = CaptureMailer()
    install(box)
    calls = []
    opens = []
    import server.accounts as accounts_module

    original_connect = accounts_module.connect

    def structured(self, model, messages, schema_name, schema, **kwargs):
        from flask import current_app

        calls.append(current_app.config["ACCOUNT_ROLE"])
        return {"response": "Talk to the team next."}

    def connect_and_note():
        from flask import current_app, has_request_context

        if has_request_context():
            opens.append(current_app.config["ACCOUNT_ROLE"])
        return original_connect()

    monkeypatch.setattr("server.venice.client.VeniceClient.structured", structured)
    monkeypatch.setattr(
        "server.venice.client.requests.Session.request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("provider")),
    )
    monkeypatch.setattr(accounts_module, "connect", connect_and_note)
    from server import create_app

    authority = create_app()
    monkeypatch.setenv("AI_PARTNER_ACCOUNT_ROLE", "proxy")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    proxy = create_app()
    forwarded = []

    def transport(method, path, data, headers, content_type):
        forwarded.append((method, path.split("?")[0]))
        response = authority.test_client().open(
            path,
            method=method,
            data=data,
            headers=headers,
            content_type=content_type,
        )
        return response.status_code, response.get_data(), response.content_type

    proxy.config["RAILWAY_TRANSPORT"] = transport
    try:
        yield {
            "authority": authority.test_client(),
            "proxy": proxy.test_client(),
            "mail": box,
            "calls": calls,
            "opens": opens,
            "forwarded": forwarded,
        }
    finally:
        reset()
        drop_test_schema(dsn, schema)


def test_magic_link_signs_in_without_putting_the_token_in_the_response(world):
    asked = world["proxy"].post("/api/auth/request", json={"email": "Ada@Example.com"})
    assert asked.status_code == 200, asked.get_json()
    assert "token" not in asked.get_json()
    assert world["mail"].outbox[0]["to"] == "ada@example.com"
    token = _token(world["mail"].outbox[0])
    first = world["proxy"].get("/api/auth/verify?token=" + token)
    assert first.status_code == 302
    me = world["proxy"].get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["email"] == "ada@example.com"
    assert me.get_json()["questions_remaining"] == 3
    again = world["proxy"].get("/api/auth/verify?token=" + token)
    assert again.status_code == 400
    world["proxy"].post("/api/auth/logout")
    assert world["proxy"].get("/api/auth/me").status_code == 401


def test_unconfigured_mailer_fails_without_a_session(world):
    reset()
    refused = world["authority"].post("/api/auth/request", json={"email": "ada@example.com"})
    assert refused.status_code == 503
    assert refused.get_json()["error"]["code"] == "mailer_unconfigured"
    assert "token" not in refused.get_data(as_text=True)
    assert world["authority"].get("/api/auth/me").status_code == 401


def _paid_state(chat_id, message):
    return {
        "message": message,
        "state": {
            "chat_id": chat_id,
            "phase": "research",
            "problem": "Plant margins",
            "team": "finance",
            "tools": "sheets",
            "maturity": 2,
            "calls": 0,
        },
    }


def test_intake_does_not_use_a_question_and_three_questions_then_stop(world):
    world["proxy"].post("/api/auth/request", json={"email": "ada@example.com"})
    token = _token(world["mail"].outbox[0])
    assert world["proxy"].get("/api/auth/verify?token=" + token).status_code == 302
    intake = world["proxy"].post("/api/chat", json={"message": "We make parts for machines.", "state": {}})
    assert intake.status_code == 200
    assert str(intake.get_json()["state"]["phase"]).startswith("ask_")
    assert intake.get_json().get("error") is None
    anonymous = world["proxy"].application.test_client().post("/api/chat", json=_paid_state("anon", "Run it"))
    assert anonymous.status_code == 403
    assert anonymous.get_json()["error"]["code"] == "sign_in_required"
    for index in range(3):
        paid = world["proxy"].post("/api/chat", json=_paid_state(f"chat-{index}", f"Question {index}"))
        assert paid.status_code == 200, paid.get_data(as_text=True)
    blocked = world["proxy"].post("/api/chat", json=_paid_state("chat-3", "One more"))
    assert blocked.status_code == 403
    assert blocked.get_json()["error"]["code"] == "questions_exhausted"
    cookie = world["proxy"].get_cookie("ai_partner_session")
    direct = world["authority"].post(
        "/api/chat",
        json=_paid_state("chat-direct", "From Railway itself."),
        headers={"X-AI-Partner-Session": cookie.value},
    )
    assert direct.status_code == 403
    assert direct.get_json()["error"]["code"] == "questions_exhausted"
    assert "proxy" not in world["opens"]
    with world["authority"].application.test_request_context():
        report = usage_report()
    assert report["signups"] == 1
    assert report["users"][0]["questions_used"] == 3
    assert report["users"][0]["questions_remaining"] == 0
    run = report["runs"][0]
    assert run["reserved_microusd"] is None
    assert run["calculated_microusd"] is None
    assert run["billed_microusd"] is None
    with world["authority"].application.test_request_context():
        set_run_costs(run["id"], calculated=42)
        after = usage_report()["runs"][0]
    assert after["calculated_microusd"] == 42
    assert after["billed_microusd"] is None
    assert after["reserved_microusd"] is None


def test_automatic_phase_continuations_share_one_question(world):
    world["proxy"].post("/api/auth/request", json={"email": "ada@example.com"})
    token = _token(world["mail"].outbox[0])
    assert world["proxy"].get("/api/auth/verify?token=" + token).status_code == 302
    first = world["proxy"].post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert first.status_code == 200, first.get_data(as_text=True)
    state = first.get_json()["state"]
    before = len(world["calls"])
    for _ in range(4):
        follow = world["proxy"].post("/api/chat", json={"message": "", "state": state})
        assert follow.status_code == 200, follow.get_data(as_text=True)
        state = follow.get_json()["state"]
    assert len(world["calls"]) > before
    with world["authority"].application.test_request_context():
        report = usage_report()
    assert report["users"][0]["questions_used"] == 1
    state = dict(state)
    state["phase"] = "research"
    again = world["proxy"].post("/api/chat", json={"message": "Change the recommendation.", "state": state})
    assert again.status_code == 200, again.get_data(as_text=True)
    with world["authority"].application.test_request_context():
        assert usage_report()["users"][0]["questions_used"] == 2


def test_proxied_sign_in_limits_follow_the_browser(world):
    for n in range(5):
        sent = world["authority"].post("/api/auth/request", json={"email": f"local{n}@example.com"})
        assert sent.status_code == 200, sent.get_json()
    blocked = world["authority"].post("/api/auth/request", json={"email": "local5@example.com"})
    assert blocked.status_code == 429
    other = world["proxy"].post(
        "/api/auth/request",
        json={"email": "browser@example.com"},
        headers={"X-Real-IP": "203.0.113.50"},
    )
    assert other.status_code == 200, other.get_json()


def test_chat_stays_open_until_a_mailer_is_configured(world):
    reset()
    opened = world["authority"].post(
        "/api/chat",
        json={"message": "We make parts for machines.", "visitor_id": "visitor-1", "state": {}},
    )
    assert opened.status_code == 200
    assert opened.get_json().get("error") is None
    with world["authority"].application.test_request_context():
        report = usage_report()
    assert report["sources"]["web"]["connections"] == 1
    assert any(item["identity"] == "visitor-1" for item in report["connections"])


def test_a_second_link_does_not_grant_more_questions(world):
    world["authority"].post("/api/auth/request", json={"email": "ada@example.com"})
    token = _token(world["mail"].outbox[0])
    issued = world["authority"].post("/api/auth/verify", json={"token": token})
    assert issued.status_code == 200
    session = issued.get_json()["session_token"]
    headers = {"X-AI-Partner-Session": session}
    for index in range(3):
        sent = world["authority"].post("/api/chat", json=_paid_state(f"again-{index}", "A question."), headers=headers)
        assert sent.status_code == 200, sent.get_data(as_text=True)
    world["authority"].post("/api/auth/request", json={"email": "ada@example.com"})
    second = _token(world["mail"].outbox[1])
    again = world["authority"].post("/api/auth/verify", json={"token": second})
    assert again.get_json()["questions_remaining"] == 0
    refused = world["authority"].post(
        "/api/chat",
        json=_paid_state("again-4", "After signing in again."),
        headers={"X-AI-Partner-Session": again.get_json()["session_token"]},
    )
    assert refused.status_code == 403
    assert refused.get_json()["error"]["code"] == "questions_exhausted"


def test_usage_page_requires_the_partner_key_and_hides_emails_until_then(world):
    world["authority"].post("/api/auth/request", json={"email": "ada@example.com"})
    hidden = world["authority"].get("/admin/usage", headers={"Accept": "application/json"})
    assert hidden.status_code == 401
    assert "ada@example.com" not in hidden.get_data(as_text=True)
    form = world["proxy"].get("/admin/usage")
    assert form.status_code == 401
    assert "ada@example.com" not in form.get_data(as_text=True)
    shown = world["proxy"].get("/admin/usage", headers={"Authorization": "Bearer partner-test-key"})
    assert shown.status_code == 200
    page = shown.get_data(as_text=True)
    assert "ada@example.com" in page
    assert 'class="usage-count">1<' in page
    assert "Questions" in page

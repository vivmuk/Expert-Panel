"""Keiki texts one contact through intake and a finished /r/<token> page. No provider network."""
import json

from server.config import Config
from tests.test_chatjob import fake_model
from tests.test_keiki import SECRET, _sign

PROBLEM = "We need a better clinic intake before the Monday rush."
PHONE = "+1 (555) 765-4321"


def _doubles(monkeypatch):
    calls = []
    monkeypatch.setenv("AI_PARTNER_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr("server.api.agents.complete_with_venice", fake_model(calls))
    monkeypatch.setattr("server.api.agents.exa_search", lambda query, limit=4: [])
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    return calls


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("KEIKI_HARNESS_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("KEIKI_AGENT_ID", "agent-1")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "ai-partner.up.railway.app")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server.api import keiki
    from server import create_app

    keiki.reset_conversations()
    keiki.reset_replays()
    return create_app().test_client(), keiki


def _post(client, keiki, turn_id, text, posted):
    raw = json.dumps(
        {
            "type": "keiki.turn",
            "turnId": turn_id,
            "agentId": "agent-1",
            "conversationId": turn_id,
            "channel": {"channel": "sms", "phone": PHONE},
            "messages": [{"text": text}],
            "keiki": {"turnUrl": f"https://keiki.example/turns/{turn_id}"},
        }
    ).encode()
    posted.clear()
    monkey_thread(keiki)
    response = client.post(
        "/keiki/turn",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "Keiki-Signature": _sign(raw),
            "Keiki-Turn-Token": "turn-token",
        },
    )
    return response


def monkey_thread(keiki):
    real = keiki.threading.Thread

    def factory(*args, **kwargs):
        target = kwargs.get("target")
        if target is keiki.run_turn:
            class _Inline:
                def start(self):
                    target(*kwargs["args"])

            return _Inline()
        return real(*args, **kwargs)

    keiki.threading.Thread = factory


def _texts(posted):
    return [body.get("text") for _url, body in posted if body.get("text")]


def test_contact_key_ignores_the_turn_id():
    from server.api.keiki import contact_key

    key = contact_key(
        {
            "agentId": "agent-1",
            "turnId": "t1",
            "conversationId": "t1",
            "channel": {"channel": "sms", "phone": PHONE},
            "keiki": {"turnUrl": "https://keiki.example/turns/t1"},
        }
    )
    assert key == ("agent-1", "+15557654321")


def test_three_turns_from_one_contact_reach_a_results_page(monkeypatch, tmp_path):
    calls = _doubles(monkeypatch)
    client, keiki = _client(monkeypatch, tmp_path)
    posted = []
    monkeypatch.setattr(keiki, "_post", lambda url, token, body: posted.append((url, body)))

    first = _post(client, keiki, "t1", PROBLEM, posted)
    assert first.status_code == 202
    opening = _texts(posted)
    assert opening
    assert "about 4 minutes" not in opening[0]
    assert "Invoice-led" not in opening[0]
    assert posted[-1][1] == {"status": "completed"}
    assert calls == ["ChatIntake"]

    keiki._states.clear()
    second = _post(client, keiki, "t2", "The front desk owns scheduling and the rooms back up.", posted)
    assert second.status_code == 202
    follow = _texts(posted)
    assert follow and follow[0] != opening[0]
    assert "about 4 minutes" not in follow[0]
    assert calls == ["ChatIntake"]

    third = _post(client, keiki, "t3", "one team", posted)
    assert third.status_code == 202
    texts = _texts(posted)
    assert texts[0].startswith("Hi, this is AI Partner")
    assert "about 4 minutes" in texts[0]
    assert texts.count(texts[0]) == 1
    assert not any("Experts " in text for text in texts)
    assert not any(text.startswith("Job.") for text in texts)
    link = texts[-1]
    assert link.startswith("Your engagement is ready.")
    assert "https://ai-partner.up.railway.app/r/" in link
    assert posted[-1][1] == {"status": "completed"}
    token = link.split("/r/", 1)[1].split(" ", 1)[0]
    page = client.get(f"/r/{token}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "text/html" in page.content_type
    assert PROBLEM in html
    assert f"/r/{token}/report.md" in html
    assert f"/r/{token}/deck.pptx" in html
    assert f"/r/{token}/kit.zip" in html
    assert f"/r/{token}/skill-pack.zip" in html
    assert "Pilot-led" in html or "maturity" in html.lower()
    report = client.get(f"/r/{token}/report.md")
    assert report.status_code == 200
    assert PROBLEM in report.get_data(as_text=True)
    kit = client.get(f"/r/{token}/kit.zip")
    assert kit.status_code == 200
    assert kit.mimetype == "application/zip"
    missing = client.get("/r/not-a-real-token")
    assert missing.status_code == 404
    assert "ChatResearch" in calls
    assert "ChatChart" in calls


def test_engine_failure_sends_an_apology_without_the_traceback(monkeypatch, tmp_path):
    _doubles(monkeypatch)
    client, keiki = _client(monkeypatch, tmp_path)
    posted = []
    monkeypatch.setattr(keiki, "_post", lambda url, token, body: posted.append((url, body)))

    def explode(message, state):
        raise RuntimeError("secret stack detail")

    monkeypatch.setattr(keiki, "_engine", explode)
    response = _post(client, keiki, "bad-1", PROBLEM, posted)
    assert response.status_code == 202
    blob = json.dumps([body for _url, body in posted])
    assert "snag" in blob
    assert "secret stack detail" not in blob
    assert "Traceback" not in blob
    assert posted[-1][1] == {"status": "failed"}


def test_unknown_results_token_is_404(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    from server import create_app

    client = create_app().test_client()
    missing = client.get("/r/" + "a" * 43)
    assert missing.status_code == 404

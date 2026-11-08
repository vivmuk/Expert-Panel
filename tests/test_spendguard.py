"""Paid work stays closed unless a calculated reservation can be stored.

These tests do not call Venice, Exa, or Supermemory. A missing price is not
treated as free. Two ledger files are two hosts, not one shared cap.
"""
import threading

import pytest

from server.api.chat import complete_with_venice
from server.spendguard import SpendClosed, phase_key, run_paid_phase
from tests.test_chatjob import ONE_SHOT


class Boom(Exception):
    pass


@pytest.fixture
def provider_spies(monkeypatch):
    calls = []

    def boom(*_args, **_kwargs):
        calls.append("network")
        raise AssertionError("provider I/O")

    monkeypatch.setattr("server.venice.client.requests.Session.request", boom)
    monkeypatch.setattr("server.exa_search.requests.post", boom)
    monkeypatch.setattr("server.chatmemory.requests.post", boom)
    monkeypatch.setattr("server.api.voice.requests.post", boom)
    monkeypatch.setattr("server.pipeline.runner.get_catalog", boom)
    monkeypatch.setattr("server.api.branding.get_catalog", boom)
    return calls


def _client():
    from server import create_app

    return create_app().test_client()


def test_unpaid_intake_does_not_call_a_provider(provider_spies):
    client = _client()
    res = client.post("/api/chat", json={"message": "We make parts for machines.", "state": {}})
    body = res.get_json()
    assert res.status_code == 200
    assert body["state"]["phase"] == "ask_context"
    assert body.get("error") is None
    assert provider_spies == []


def test_paid_chat_is_closed_before_any_provider_call(provider_spies):
    client = _client()
    res = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    body = res.get_json()
    assert res.status_code == 403
    assert body["error"]["code"] == "spend_ledger_unavailable"
    assert body["next"] is None
    assert provider_spies == []


def test_stateless_maritime_source_is_closed(provider_spies):
    client = _client()
    res = client.post("/chat", json={"message": "Hello from a channel", "source": "maritime"})
    body = res.get_json()
    assert res.status_code == 403
    assert body["error"]["code"] == "spend_ledger_unavailable"
    assert provider_spies == []


def test_catalog_artifact_and_exa_and_memory_are_closed(provider_spies, monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "present-but-not-used")
    client = _client()
    artifact = client.post(
        "/api/chat/artifact",
        json={"artifact_id": "research-brief", "state": {"problem": "Parts", "phase": "done"}},
    )
    assert artifact.status_code == 403
    assert artifact.get_json()["error"]["code"] == "spend_ledger_unavailable"
    with pytest.raises(SpendClosed) as exc:
        from server.exa_search import exa_search

        exa_search("margin benchmarks")
    assert exc.value.code == "paid_path_blocked"
    with pytest.raises(SpendClosed):
        from server.chatmemory import recall

        recall("chat", "query")
    assert provider_spies == []


def test_legacy_run_is_blocked_before_the_catalog(provider_spies, monkeypatch):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "static-test-key")
    client = _client()
    res = client.post(
        "/api/runs",
        json={"input": {"problem": "A hypothetical plant network."}},
        headers={"Authorization": "Bearer static-test-key"},
    )
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "paid_path_blocked"
    assert provider_spies == []


def test_voice_catalog_estimate_and_brand_are_closed(provider_spies):
    client = _client()
    voice = client.post("/api/voice/plan", json={"text": "open the deck"})
    assert voice.status_code == 403
    assert voice.get_json()["error"]["code"] == "spend_ledger_unavailable"
    models = client.get("/api/models")
    assert models.status_code == 403
    assert models.get_json()["error"]["code"] == "paid_path_blocked"
    estimate = client.post("/api/estimate", json={"mode": "deep_dive", "panelSize": 20})
    assert estimate.status_code == 403
    assert estimate.get_json()["error"]["code"] == "paid_path_blocked"
    from server.api.branding import _generate_slot

    with pytest.raises(SpendClosed) as brand:
        _generate_slot("hero")
    assert brand.value.code == "spend_ledger_unavailable"
    assert provider_spies == []


def test_direct_model_client_is_blocked_without_a_phase(provider_spies):
    with pytest.raises(SpendClosed) as exc:
        complete_with_venice("ChatReply", [{"role": "user", "content": "Hi"}], {"type": "object"}, 50)
    assert exc.value.code == "spend_ledger_unavailable"
    assert provider_spies == []


def _open_ledger(monkeypatch, tmp_path, ceiling="1000", venice="10", exa="4", memory="7"):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER", "sqlite")
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER_PATH", str(tmp_path / "spend.db"))
    monkeypatch.setenv("AI_PARTNER_CALCULATED_CEILING_MICROUSD", ceiling)
    if venice is None:
        monkeypatch.delenv("AI_PARTNER_CALCULATED_MICROUSD_VENICE_ATTEMPT", raising=False)
    else:
        monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_VENICE_ATTEMPT", venice)
    if exa is None:
        monkeypatch.delenv("AI_PARTNER_CALCULATED_MICROUSD_EXA", raising=False)
    else:
        monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_EXA", exa)
    if memory is None:
        monkeypatch.delenv("AI_PARTNER_CALCULATED_MICROUSD_MEMORY", raising=False)
    else:
        monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_MEMORY", memory)


def _state(chat_id="chat-a", phase="synthesize", problem="Keep the problem"):
    return {
        "chat_id": chat_id,
        "phase": phase,
        "problem": problem,
        "team": "finance",
        "tools": "spreadsheets",
        "maturity": 2,
        "experts": [],
        "debate_done": 0,
        "size": "",
        "calls": 0,
        "status": "settled",
    }


def test_missing_zero_and_negative_prices_are_not_free(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path, venice=None)
    with pytest.raises(SpendClosed) as missing:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert missing.value.code == "calculated_price_unavailable"
    _open_ledger(monkeypatch, tmp_path, venice="0")
    with pytest.raises(SpendClosed) as zero:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert zero.value.code == "calculated_price_unavailable"
    _open_ledger(monkeypatch, tmp_path, venice="-3")
    with pytest.raises(SpendClosed) as negative:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert negative.value.code == "calculated_price_unavailable"


def test_unset_ceiling_is_not_a_free_pass(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path, ceiling="")
    with pytest.raises(SpendClosed) as exc:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert exc.value.code == "currency_bound_unavailable"


def test_replay_returns_the_recorded_result_and_uncertain_does_not_retry(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path)
    calls = []

    def work():
        calls.append(1)
        return {"reply": "recorded", "state": {"phase": "panel", "chat_id": "chat-a"}, "next": "panel"}

    first = run_paid_phase(_state(), work)
    second = run_paid_phase(_state(problem="Keep the problem"), work)
    assert first == second
    assert calls == [1]
    assert phase_key(_state()) == phase_key({**_state(), "calls": 0, "sig": "forged", "status": "settled"})

    def crash():
        calls.append("crash")
        raise Boom("after send")

    with pytest.raises(Boom):
        run_paid_phase(_state(chat_id="chat-b"), crash)
    with pytest.raises(SpendClosed) as uncertain:
        run_paid_phase(_state(chat_id="chat-b"), crash)
    assert uncertain.value.code == "phase_uncertain"
    assert calls == [1, "crash"]


def test_a_different_chat_does_not_receive_another_chats_result(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path)
    seen = []

    def work():
        seen.append("run")
        return {"reply": "one"}

    run_paid_phase(_state(chat_id="one"), work)
    run_paid_phase(_state(chat_id="two"), work)
    assert seen == ["run", "run"]


def test_parallel_callers_send_the_phase_once(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path)
    calls = []
    entered = threading.Event()
    release = threading.Event()

    def work():
        calls.append(1)
        entered.set()
        assert release.wait(timeout=2)
        return {"reply": "once"}

    errors = []

    def runner():
        try:
            run_paid_phase(_state(chat_id="same"), work)
        except SpendClosed as exc:
            errors.append(exc.code)

    threads = [threading.Thread(target=runner), threading.Thread(target=runner)]
    for thread in threads:
        thread.start()
    assert entered.wait(timeout=2)
    for _ in range(40):
        if errors:
            break
        threading.Event().wait(0.05)
    release.set()
    for thread in threads:
        thread.join(timeout=2)
    assert calls == [1]
    assert errors == ["phase_uncertain"]


def test_two_ledger_files_do_not_share_a_settled_phase(monkeypatch, tmp_path):
    calls = []

    def work():
        calls.append(1)
        return {"reply": "host"}

    _open_ledger(monkeypatch, tmp_path)
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER_PATH", str(tmp_path / "host-a.db"))
    run_paid_phase(_state(), work)
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER_PATH", str(tmp_path / "host-b.db"))
    run_paid_phase(_state(), work)
    assert calls == [1, 1]


def test_calculated_ceiling_stops_before_the_call(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path, ceiling="2", venice="10")
    with pytest.raises(SpendClosed) as exc:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert exc.value.code == "calculated_ceiling_exceeded"


def test_research_requires_an_exa_price_when_the_venice_key_is_set(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path, exa=None)
    monkeypatch.setenv("VENICE_API_KEY", "present")
    with pytest.raises(SpendClosed) as exc:
        run_paid_phase(_state(phase="research"), lambda: {"ok": True})
    assert exc.value.code == "calculated_price_unavailable"


def test_vercel_cannot_use_the_sqlite_ledger(monkeypatch, tmp_path):
    _open_ledger(monkeypatch, tmp_path)
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(SpendClosed) as exc:
        run_paid_phase(_state(), lambda: {"ok": True})
    assert exc.value.code == "spend_ledger_unavailable"


def test_opt_in_http_replay_uses_the_recorded_turn(monkeypatch, tmp_path, provider_spies):
    _open_ledger(monkeypatch, tmp_path)
    calls = []

    def fake(name, messages, schema, max_tokens):
        calls.append(name)
        return {"facts": ["The client named plants."], "service_line": "Margin recovery", "queries": ["plant margin benchmarks"]}

    fake._spend_enforced = True
    monkeypatch.setattr("server.api.chat.complete_with_venice", fake)
    monkeypatch.setattr("server.api.chat.exa_search", lambda query, limit=4: [])
    client = _client()
    state = {
        "chat_id": "fixedchat0000001",
        "phase": "research",
        "problem": "Hypothetical plant margins.",
        "team": "finance and plant leads",
        "tools": "ERP and spreadsheets",
        "maturity": 2,
        "calls": 0,
    }
    first = client.post("/api/chat", json={"message": "", "state": state})
    assert first.status_code == 200, first.get_json()
    second = client.post("/api/chat", json={"message": "", "state": state})
    assert second.status_code == 200
    assert second.get_json()["reply"] == first.get_json()["reply"]
    assert second.get_json()["state"]["phase"] == first.get_json()["state"]["phase"]
    assert calls == ["ChatResearch"]
    assert provider_spies == []

"""Engagement exposure through the real entry points. No provider sockets.

5000000 microusd and 3 executions are application limits. They are not a
provider invoice. HTTP does not install an authority.
"""
import hashlib
import json
import threading

import pytest

from server.api.branding import _generate_slot
from server.api.chat import complete_with_venice
from server.api.voice import _planned
from server.chatmemory import recall, remember
from server.exa_search import exa_search
from server.exposure import (
    APPLICATION_CEILING_MICROUSD,
    MAX_ENGAGEMENT_ATTEMPTS,
    ExposureStop,
    MemoryAuthority,
    OfflineTransport,
    UncertainOutcome,
    VENICE_UPSTREAM_TRIES,
    run_execution,
)
from server.spendguard import SpendClosed, run_paid_phase
from tests.test_chatjob import ONE_SHOT


class Recording(OfflineTransport):
    def __init__(self, authority, project, fail_at=None):
        self.authority = authority
        self.project = project
        self.fail_at = fail_at
        self.calls = []

    def _touch(self, name):
        state = self.authority.accounted(self.project["project_id"], self.project["seal"])
        assert state["reserved_microusd"] > 0
        self.calls.append(name)
        if self.fail_at == len(self.calls):
            raise UncertainOutcome()

    def venice(self):
        self._touch("venice")
        return {"ok": True}

    def search(self):
        self._touch("exa")
        return []

    def recall(self):
        self._touch("memory")
        return ""

    def remember(self):
        self._touch("memory-write")
        return None

    def voice(self):
        self._touch("voice")
        return None

    def image(self):
        self._touch("image")
        return None


def _plan():
    return [
        {"service": "venice", "calls": 1, "unit_microusd": 10},
        {"service": "exa", "calls": 1, "unit_microusd": 4},
        {"service": "memory", "calls": 2, "unit_microusd": 7},
        {"service": "voice", "calls": 1, "unit_microusd": 5},
        {"service": "image", "calls": 1, "unit_microusd": 6},
    ]


def _expected_reserve():
    return 10 * VENICE_UPSTREAM_TRIES + 4 + 7 * 2 + 5 + 6


def _work():
    complete_with_venice("name", [{"role": "user", "content": "secret prompt"}], {}, 8)
    exa_search("secret query")
    recall("chat", "secret query")
    remember("chat", "secret body")
    _planned("secret heard")
    _generate_slot("mark", prompt="secret image")
    return "stored-result-token"


def test_one_execution_covers_every_service_and_venice_retries(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "offline-memory")
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project)
    done = run_execution(authority, project["project_id"], project["seal"], _plan(), transport, _work)
    assert done["kind"] == "settled"
    assert done["reserved_microusd"] == _expected_reserve()
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    state = authority.accounted(project["project_id"], project["seal"])
    assert state["engagement_attempts"] == 1
    assert state["engagement_attempt_cap_enforced"] is True
    assert VENICE_UPSTREAM_TRIES > 1
    again = run_execution(
        authority,
        project["project_id"],
        project["seal"],
        _plan(),
        transport,
        _work,
        execution_id=done["execution_id"],
    )
    assert again["kind"] == "reuse"
    assert again["result"] == "stored-result-token"
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1
    view = authority.report(project["project_id"], project["seal"])
    dumped = json.dumps(view)
    assert "stored-result-token" not in dumped
    assert "secret prompt" not in dumped
    assert "secret query" not in dumped
    fingerprint = hashlib.sha256(b"venice").hexdigest()
    assert fingerprint not in dumped
    assert view["provider_invoice_cap"] is False
    assert view["engagement_attempt_cap"] == MAX_ENGAGEMENT_ATTEMPTS
    assert view["executions"][0]["billed_microusd"] is None
    venice = next(item for item in view["executions"][0]["services"] if item["service"] == "venice")
    assert venice["upstream_tries_covered"] == VENICE_UPSTREAM_TRIES
    assert venice["logical_calls"] == 1
    assert view["executions"][0]["report_id"] != fingerprint


def test_fourth_execution_stops_before_transport():
    authority = MemoryAuthority()
    project = authority.register_project()
    plan = [{"service": "venice", "calls": 1, "unit_microusd": 10}]

    def work():
        complete_with_venice("n", [], {}, 1)
        return "ok"

    for _ in range(MAX_ENGAGEMENT_ATTEMPTS):
        transport = Recording(authority, project)
        assert run_execution(authority, project["project_id"], project["seal"], plan, transport, work)["kind"] == "settled"
        assert transport.calls == ["venice"]
    transport = Recording(authority, project)
    with pytest.raises(ExposureStop) as exc:
        run_execution(authority, project["project_id"], project["seal"], plan, transport, work)
    assert exc.value.code == "attempts_exhausted"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 3


def test_reservation_cannot_cross_five_dollars_and_a_missing_price_does_not_send():
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project)
    over = [{"service": "venice", "calls": 1, "unit_microusd": APPLICATION_CEILING_MICROUSD}]
    with pytest.raises(ExposureStop) as exc:
        run_execution(authority, project["project_id"], project["seal"], over, transport, _work)
    assert exc.value.code == "over_cap"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0
    with pytest.raises(ExposureStop) as missing:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            [{"service": "exa", "calls": 1, "unit_microusd": 0}],
            transport,
            _work,
        )
    assert missing.value.code == "price_unknown"
    assert transport.calls == []


def test_uncertain_execution_blocks_the_next_until_reconcile(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "offline-memory")
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project, fail_at=1)
    with pytest.raises(SpendClosed) as exc:
        run_execution(authority, project["project_id"], project["seal"], _plan(), transport, _work)
    assert exc.value.code == "phase_uncertain"
    assert transport.calls == ["venice"]
    reserved = authority.accounted(project["project_id"], project["seal"])["reserved_microusd"]
    assert reserved == _expected_reserve()
    quiet = Recording(authority, project)
    with pytest.raises(ExposureStop) as blocked:
        run_execution(authority, project["project_id"], project["seal"], _plan(), quiet, _work)
    assert blocked.value.code == "project_unreconciled"
    assert quiet.calls == []
    execution_id = authority._projects[project["project_id"]]["executions"][0]["execution_id"]
    authority.reconcile(project["project_id"], project["seal"], execution_id)
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == reserved
    follow = Recording(authority, project)
    done = run_execution(authority, project["project_id"], project["seal"], _plan(), follow, _work)
    assert done["kind"] == "settled"
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 2


def test_unknown_project_and_unknown_execution_do_not_mint():
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project)
    plan = [{"service": "voice", "calls": 1, "unit_microusd": 5}]

    def work():
        _planned("x")
        return "ok"

    with pytest.raises(ExposureStop) as missing:
        run_execution(authority, "client-minted", project["seal"], plan, transport, work)
    assert missing.value.code == "project_rejected"
    with pytest.raises(ExposureStop) as unknown:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            plan,
            transport,
            work,
            execution_id="client-chosen",
        )
    assert unknown.value.code == "execution_rejected"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_a_call_past_the_plan_does_not_send_and_keeps_the_reservation():
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project)
    plan = [{"service": "venice", "calls": 1, "unit_microusd": 10}]

    def work():
        complete_with_venice("n", [], {}, 1)
        complete_with_venice("n", [], {}, 1)
        return "ok"

    with pytest.raises(SpendClosed) as exc:
        run_execution(authority, project["project_id"], project["seal"], plan, transport, work)
    assert exc.value.code == "paid_path_blocked"
    assert transport.calls == ["venice"]
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 10 * VENICE_UPSTREAM_TRIES
    with pytest.raises(ExposureStop) as blocked:
        run_execution(authority, project["project_id"], project["seal"], plan, Recording(authority, project), work)
    assert blocked.value.code == "project_unreconciled"


def test_two_authorities_are_not_one_cap():
    plan = [{"service": "venice", "calls": 1, "unit_microusd": APPLICATION_CEILING_MICROUSD // VENICE_UPSTREAM_TRIES}]
    first = MemoryAuthority()
    second = MemoryAuthority()
    one = first.register_project()
    two = second.register_project()

    def work():
        complete_with_venice("n", [], {}, 1)
        return "ok"

    assert run_execution(first, one["project_id"], one["seal"], plan, Recording(first, one), work)["kind"] == "settled"
    assert run_execution(second, two["project_id"], two["seal"], plan, Recording(second, two), work)["kind"] == "settled"
    assert first.accounted(one["project_id"], one["seal"])["reserved_microusd"] == APPLICATION_CEILING_MICROUSD // VENICE_UPSTREAM_TRIES * VENICE_UPSTREAM_TRIES


def test_http_does_not_install_an_authority_or_open_a_cost_route(monkeypatch):
    authority = MemoryAuthority()
    monkeypatch.delenv("VERCEL", raising=False)
    from server import create_app

    client = create_app().test_client()
    res = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "currency_bound_unavailable"
    rules = [rule.rule for rule in client.application.url_map.iter_rules()]
    assert not any("cost" in rule or "budget" in rule or "exposure" in rule for rule in rules)
    with pytest.raises(SpendClosed):
        complete_with_venice("n", [], {}, 1)
    calls = []
    with pytest.raises(SpendClosed):
        run_paid_phase({}, lambda: calls.append("ran"))
    assert calls == []


def test_an_error_before_any_send_does_not_consume_an_attempt():
    authority = MemoryAuthority()
    project = authority.register_project()
    transport = Recording(authority, project)

    def work():
        raise RuntimeError("stopped before a call")

    with pytest.raises(RuntimeError):
        run_execution(authority, project["project_id"], project["seal"], _plan(), transport, work)
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_parallel_begins_cannot_both_cross_the_ceiling():
    authority = MemoryAuthority()
    project = authority.register_project()
    plan = [{"service": "memory", "calls": 1, "unit_microusd": 3_000_000}]
    barrier = threading.Barrier(2)
    outcomes = []

    def once():
        barrier.wait()
        try:
            outcomes.append(authority.begin(project["project_id"], project["seal"], plan)["kind"])
        except ExposureStop as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["over_cap", "reserved"]
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 3_000_000
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1

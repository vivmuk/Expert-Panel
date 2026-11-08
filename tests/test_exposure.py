"""Offline exposure contract. Synthetic prices only. No provider sockets.

These tests do not establish a production $5 cap. Postgres is not connected.
"""
import contextvars
import sqlite3
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
    POSTGRES_INTEGRATION,
    ExposureStop,
    MemoryAuthority,
    OfflineTransport,
    UncertainOutcome,
    VENICE_UPSTREAM_TRIES,
    describe_exa,
    describe_image,
    describe_recall,
    describe_remember,
    describe_venice,
    describe_voice,
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
        self.payloads = []

    def _touch(self, name):
        state = self.authority.accounted(self.project["project_id"], self.project["seal"])
        assert state["reserved_microusd"] > 0
        self.calls.append(name)
        if self.fail_at == len(self.calls):
            raise UncertainOutcome()

    def venice(self, request):
        self._touch("venice")
        self.payloads.append(request["payload"])
        return {"ok": True}

    def search(self, request):
        self._touch("exa")
        self.payloads.append(request["payload"])
        return []

    def recall(self, request):
        self._touch("memory")
        self.payloads.append(request["payload"])
        return ""

    def remember(self, request):
        self._touch("memory-write")
        self.payloads.append(request["payload"])
        return None

    def voice(self, request):
        self._touch("voice")
        self.payloads.append(request["payload"])
        return None

    def image(self, request):
        self._touch("image")
        self.payloads.append(request["payload"])
        return None


def _row(service, unit, upstream, repair=0):
    return {
        "service": service,
        "model": "offline",
        "max_input_bytes": 2000,
        "max_output_tokens": 200,
        "max_duration_seconds": 60,
        "max_items": 4,
        "upstream_tries": upstream,
        "repair_tries": repair,
        "unit_microusd": unit,
        "provenance": "synthetic",
    }


def _schedule():
    return [
        _row("venice", 10, VENICE_UPSTREAM_TRIES, 1),
        _row("exa", 4, 1, 0),
        _row("memory", 7, 1, 0),
        _row("voice", 5, 1, 0),
        _row("image", 6, 1, 0),
    ]


def _authority():
    return MemoryAuthority(_schedule())


def _req(service, payload, output_tokens=8):
    if service == "venice":
        return describe_venice("offline", [{"role": "user", "content": payload}], {}, output_tokens)
    if service == "exa":
        return describe_exa(payload, 1)
    if service == "memory":
        return describe_recall("chat", payload)
    if service == "voice":
        return describe_voice("plan", payload)
    if service == "image":
        return describe_image("mark", payload, "offline")
    raise AssertionError(service)


def _requests(tag):
    return [
        describe_venice("offline", [{"role": "user", "content": f"prompt-{tag}"}], {}, 8),
        describe_exa(f"query-{tag}", 1),
        describe_recall("chat", f"recall-{tag}"),
        describe_remember("chat", f"remember-{tag}"),
        describe_voice("plan", f"heard-{tag}"),
        describe_image("mark", f"image-{tag}", "offline"),
    ]


def _expected_reserve():
    return 10 * (VENICE_UPSTREAM_TRIES + 1) + 4 + 7 * 2 + 5 + 6


def _work():
    complete_with_venice("offline", [{"role": "user", "content": "prompt-one"}], {}, 8)
    exa_search("query-one", 1)
    recall("chat", "recall-one")
    remember("chat", "remember-one")
    _planned("heard-one")
    _generate_slot("mark", "image-one", "offline")
    return "stored-result-token"


def test_synthetic_schedule_bounds_one_execution_and_replay_is_the_same_request(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "offline-memory")
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)
    requests = _requests("one")
    done = run_execution(authority, project["project_id"], project["seal"], requests, transport, _work)
    assert done["kind"] == "settled"
    assert done["reserved_microusd"] == _expected_reserve()
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    assert transport.payloads[0] == _requests("one")[0]["payload"]
    state = authority.accounted(project["project_id"], project["seal"])
    assert state["engagement_attempts"] == 1
    assert state["verified_price"] is False
    assert state["postgres_integration"] == "pending"
    assert VENICE_UPSTREAM_TRIES > 1
    requests.append(_req("venice", "mutated-after-reserve"))
    requests[0]["output_tokens"] = 10_000
    again = run_execution(
        authority,
        project["project_id"],
        project["seal"],
        _requests("one"),
        transport,
        _work,
        execution_id=done["execution_id"],
    )
    assert again["kind"] == "reuse"
    assert again["result"] == "stored-result-token"
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1
    with pytest.raises(ExposureStop) as mismatch:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            _requests("changed"),
            transport,
            _work,
            execution_id=done["execution_id"],
        )
    assert mismatch.value.code == "request_mismatch"
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    view = authority.report(project["project_id"], project["seal"])
    assert view["production_cap"] is False
    assert view["price_provenance"] == "synthetic"
    assert view["verified_price"] is False
    assert view["provider_invoice_cap"] is False
    assert "synthetic_price_not_a_verified_bound" in view["gaps"]
    assert "stored-result-token" not in str(view)
    venice = next(item for item in view["executions"][0]["services"] if item["service"] == "venice")
    assert venice["upstream_tries"] == VENICE_UPSTREAM_TRIES
    assert venice["repair_tries"] == 1


def test_caller_price_and_over_envelope_do_not_reserve():
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)
    priced = _req("venice", "body")
    priced["unit_microusd"] = 1
    with pytest.raises(ExposureStop) as rejected:
        run_execution(authority, project["project_id"], project["seal"], [priced], transport, _work)
    assert rejected.value.code == "plan_rejected"
    wide = _req("venice", "body", output_tokens=10_000)
    with pytest.raises(ExposureStop) as envelope:
        run_execution(authority, project["project_id"], project["seal"], [wide], transport, _work)
    assert envelope.value.code == "envelope_rejected"
    with pytest.raises(ExposureStop) as missing:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            [_req("venice", "body") | {"model": "not-on-the-schedule"}],
            transport,
            _work,
        )
    assert missing.value.code == "price_unknown"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_mutating_the_request_list_cannot_widen_the_reserved_snapshot():
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)
    requests = [_req("venice", "once")]

    def work():
        requests[0]["output_tokens"] = 1
        requests.extend(_req("venice", f"extra-{i}") for i in range(100))
        complete_with_venice("offline", [{"role": "user", "content": "once"}], {}, 8)
        complete_with_venice("offline", [{"role": "user", "content": "once"}], {}, 8)
        return "ok"

    with pytest.raises(SpendClosed) as exc:
        run_execution(authority, project["project_id"], project["seal"], requests, transport, work)
    assert exc.value.code == "paid_path_blocked"
    assert transport.calls == ["venice"]
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 10 * (VENICE_UPSTREAM_TRIES + 1)
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1


def _venice_work(text):
    def work():
        complete_with_venice("offline", [{"role": "user", "content": text}], {}, 8)
        return "ok"

    return work


def test_fourth_distinct_request_stops_before_transport():
    authority = _authority()
    project = authority.register_project()

    for index in range(MAX_ENGAGEMENT_ATTEMPTS):
        transport = Recording(authority, project)
        text = f"attempt-{index}"
        assert run_execution(
            authority, project["project_id"], project["seal"], [_req("venice", text)], transport, _venice_work(text)
        )["kind"] == "settled"
        assert transport.calls == ["venice"]
    transport = Recording(authority, project)
    with pytest.raises(ExposureStop) as exc:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            [_req("venice", "attempt-extra")],
            transport,
            _venice_work("attempt-extra"),
        )
    assert exc.value.code == "attempts_exhausted"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 3


def test_schedule_ceiling_and_a_missing_row_do_not_send():
    schedule = [_row("venice", APPLICATION_CEILING_MICROUSD, VENICE_UPSTREAM_TRIES, 1)]
    authority = MemoryAuthority(schedule)
    project = authority.register_project()
    transport = Recording(authority, project)
    with pytest.raises(ExposureStop) as exc:
        run_execution(authority, project["project_id"], project["seal"], [_req("venice", "big")], transport, _work)
    assert exc.value.code == "over_cap"
    bare = MemoryAuthority([_row("voice", 5, 1, 0)])
    other = bare.register_project()
    with pytest.raises(ExposureStop) as missing:
        run_execution(bare, other["project_id"], other["seal"], [_req("exa", "q")], transport, _work)
    assert missing.value.code == "price_unknown"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_uncertain_execution_blocks_a_different_request_until_reconcile(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "offline-memory")
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project, fail_at=1)
    with pytest.raises(SpendClosed) as exc:
        run_execution(authority, project["project_id"], project["seal"], _requests("one"), transport, _work)
    assert exc.value.code == "phase_uncertain"
    assert transport.calls == ["venice"]
    reserved = authority.accounted(project["project_id"], project["seal"])["reserved_microusd"]
    assert reserved == _expected_reserve()
    quiet = Recording(authority, project)
    with pytest.raises(ExposureStop) as blocked:
        run_execution(authority, project["project_id"], project["seal"], _requests("next"), quiet, _work)
    assert blocked.value.code == "project_unreconciled"
    assert quiet.calls == []
    execution_id = authority._projects[project["project_id"]]["executions"][0]["execution_id"]
    authority.reconcile(project["project_id"], project["seal"], execution_id)
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == reserved
    follow = Recording(authority, project)
    done = run_execution(
        authority, project["project_id"], project["seal"], [_req("venice", "next-body")], follow, _venice_work("next-body")
    )
    assert done["kind"] == "settled"
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 2


def test_authorize_fails_after_uncertainty_and_after_settlement():
    authority = _authority()
    project = authority.register_project()
    first = authority.begin(project["project_id"], project["seal"], [_req("venice", "a")])
    second = authority.begin(project["project_id"], project["seal"], [_req("venice", "b")])
    authority.mark_uncertain(project["project_id"], project["seal"], first["execution_id"])
    with pytest.raises(SpendClosed):
        authority.authorize_send(
            project["project_id"], project["seal"], second["execution_id"], second["capability"], _req("venice", "b")
        )
    assert authority._projects[project["project_id"]]["executions"][1]["sends"] == 0


def test_a_child_context_cannot_send_after_settlement():
    authority = _authority()
    project = authority.register_project()
    box = {}

    def work():
        box["ctx"] = contextvars.copy_context()
        complete_with_venice("offline", [{"role": "user", "content": "child"}], {}, 8)
        return "ok"

    transport = Recording(authority, project)
    done = run_execution(authority, project["project_id"], project["seal"], [_req("venice", "child")], transport, work)
    assert done["kind"] == "settled"

    def later():
        from server.exposure import current

        current().consume("venice")

    with pytest.raises(SpendClosed):
        box["ctx"].run(later)
    assert transport.calls == ["venice"]


def test_one_slot_cannot_be_authorized_twice():
    authority = _authority()
    project = authority.register_project()
    request = _req("venice", "slot")
    decision = authority.begin(project["project_id"], project["seal"], [request])
    barrier = threading.Barrier(2)
    outcomes = []

    def once():
        barrier.wait()
        try:
            authority.authorize_send(
                project["project_id"], project["seal"], decision["execution_id"], decision["capability"], request
            )
            outcomes.append("sent")
        except SpendClosed:
            outcomes.append("stopped")

    threads = [threading.Thread(target=once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["sent", "stopped"]
    assert authority._projects[project["project_id"]]["executions"][0]["sends"] == 1


def test_uncertainty_racing_a_send_still_blocks_the_next_authorize():
    authority = _authority()
    project = authority.register_project()
    request = _req("memory", "race")
    decision = authority.begin(project["project_id"], project["seal"], [request])
    barrier = threading.Barrier(2)
    outcomes = []

    def stop():
        barrier.wait()
        authority.mark_uncertain(project["project_id"], project["seal"], decision["execution_id"])

    def go():
        barrier.wait()
        try:
            authority.authorize_send(
                project["project_id"], project["seal"], decision["execution_id"], decision["capability"], request
            )
            outcomes.append("sent")
        except SpendClosed:
            outcomes.append("stopped")

    threads = [threading.Thread(target=stop), threading.Thread(target=go)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    sends = authority._projects[project["project_id"]]["executions"][0]["sends"]
    assert sends in (0, 1)
    with pytest.raises(SpendClosed):
        authority.authorize_send(
            project["project_id"], project["seal"], decision["execution_id"], decision["capability"], request
        )


def test_initialization_failure_after_reserve_voids_the_unsent_row(monkeypatch):
    authority = _authority()
    project = authority.register_project()

    def explode(decision, transport):
        raise RuntimeError("init")

    monkeypatch.setattr("server.exposure._prepare", explode)
    with pytest.raises(RuntimeError):
        run_execution(authority, project["project_id"], project["seal"], [_req("voice", "x")], Recording(authority, project), _work)
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 0


def test_unknown_project_and_unknown_execution_do_not_mint():
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)
    requests = [_req("voice", "x")]

    def work():
        _planned("x")
        return "ok"

    with pytest.raises(ExposureStop) as missing:
        run_execution(authority, "client-minted", project["seal"], requests, transport, work)
    assert missing.value.code == "project_rejected"
    with pytest.raises(ExposureStop) as unknown:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            requests,
            transport,
            work,
            execution_id="client-chosen",
        )
    assert unknown.value.code == "execution_rejected"
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_two_authorities_are_not_one_cap():
    schedule = [_row("venice", 1_000_000, VENICE_UPSTREAM_TRIES, 0)]
    first = MemoryAuthority(schedule)
    second = MemoryAuthority(schedule)
    one = first.register_project()
    two = second.register_project()

    def work():
        complete_with_venice("offline", [{"role": "user", "content": "a"}], {}, 8)
        return "ok"

    assert run_execution(first, one["project_id"], one["seal"], [_req("venice", "a")], Recording(first, one), work)["kind"] == "settled"
    assert run_execution(second, two["project_id"], two["seal"], [_req("venice", "a")], Recording(second, two), work)["kind"] == "settled"


def test_http_does_not_install_an_authority_or_open_a_cost_route(monkeypatch):
    _authority()
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
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)

    def work():
        raise RuntimeError("stopped before a call")

    with pytest.raises(RuntimeError):
        run_execution(authority, project["project_id"], project["seal"], _requests("err"), transport, work)
    assert transport.calls == []
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 0


def test_parallel_begins_cannot_both_cross_the_ceiling():
    authority = MemoryAuthority([_row("memory", 3_000_000, 1, 0)])
    project = authority.register_project()
    barrier = threading.Barrier(2)
    outcomes = []

    def once(payload):
        barrier.wait()
        try:
            outcomes.append(
                authority.begin(project["project_id"], project["seal"], [_req("memory", payload)])["kind"]
            )
        except ExposureStop as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=once, args=(f"side-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["over_cap", "reserved"]
    assert authority.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 3_000_000
    assert authority.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1


def test_helper_arguments_must_match_the_reserved_line():
    authority = _authority()
    project = authority.register_project()
    transport = Recording(authority, project)
    reserved = describe_venice("offline", [{"role": "user", "content": "declared"}], {}, 8)

    def work():
        complete_with_venice("offline", [{"role": "user", "content": "changed"}], {}, 8)
        return "ok"

    with pytest.raises(SpendClosed):
        run_execution(authority, project["project_id"], project["seal"], [reserved], transport, work)
    assert transport.calls == []
    assert transport.payloads == []
    matched = Recording(authority, project)

    def exact():
        complete_with_venice("offline", [{"role": "user", "content": "declared"}], {}, 8)
        return "ok"

    done = run_execution(authority, project["project_id"], project["seal"], [reserved], matched, exact)
    assert done["kind"] == "settled"
    assert matched.payloads == [reserved["payload"]]


def test_a_sibling_that_already_sent_cannot_settle_success_after_uncertainty():
    authority = _authority()
    project = authority.register_project()
    first = _req("venice", "first")
    second = _req("venice", "second")
    opened_a = authority.begin(project["project_id"], project["seal"], [first])
    opened_b = authority.begin(project["project_id"], project["seal"], [second])
    authority.authorize_send(
        project["project_id"], project["seal"], opened_b["execution_id"], opened_b["capability"], second
    )
    authority.mark_uncertain(project["project_id"], project["seal"], opened_a["execution_id"])
    assert authority.settle(project["project_id"], project["seal"], opened_b["execution_id"], "success-token") == "uncertain"
    rows = authority._projects[project["project_id"]]["executions"]
    assert rows[1]["status"] == "uncertain"
    assert rows[1]["result"] is None
    assert rows[1]["reserved_microusd"] == opened_b["reserved_microusd"]
    with pytest.raises(SpendClosed):
        authority.authorize_send(
            project["project_id"], project["seal"], opened_b["execution_id"], opened_b["capability"], second
        )


def test_a_voided_unsent_request_can_start_a_new_execution(monkeypatch):
    authority = _authority()
    project = authority.register_project()
    request = [_req("voice", "same")]

    def explode(decision, transport):
        raise RuntimeError("init")

    monkeypatch.setattr("server.exposure._prepare", explode)
    with pytest.raises(RuntimeError):
        run_execution(authority, project["project_id"], project["seal"], request, Recording(authority, project), _work)
    voided = authority._projects[project["project_id"]]["executions"][0]
    assert voided["status"] == "void"
    monkeypatch.undo()
    with pytest.raises(ExposureStop) as old:
        run_execution(
            authority,
            project["project_id"],
            project["seal"],
            request,
            Recording(authority, project),
            _venice_work("same"),
            execution_id=voided["execution_id"],
        )
    assert old.value.code == "execution_rejected"
    transport = Recording(authority, project)
    done = run_execution(
        authority, project["project_id"], project["seal"], request, transport, lambda: _planned("same") or "ok"
    )
    assert done["kind"] == "settled"
    assert done["execution_id"] != voided["execution_id"]
    assert transport.calls == ["voice"]
    replay = run_execution(
        authority, project["project_id"], project["seal"], request, Recording(authority, project), lambda: "nope"
    )
    assert replay["kind"] == "reuse"
    assert replay["result"] == "ok"
    barrier = threading.Barrier(2)
    outcomes = []

    def again():
        barrier.wait()
        try:
            outcomes.append(authority.begin(project["project_id"], project["seal"], [_req("voice", "other")])["kind"])
        except ExposureStop as exc:
            outcomes.append(exc.code)

    # The settled voice request is a replay. A second distinct request still reserves once under the lock.
    threads = [threading.Thread(target=again) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["attempt_uncertain", "reserved"]


def test_sqlite_conditional_update_is_the_pending_postgres_shape(tmp_path):
    """Stdlib SQLite stands in for the transaction shape. It is not the production database."""
    connection = sqlite3.connect(str(tmp_path / "contract.db"))
    connection.execute(
        "CREATE TABLE execution (id TEXT PRIMARY KEY, status TEXT, sends INTEGER, capability TEXT)"
    )
    connection.execute("INSERT INTO execution VALUES ('e', 'reserved', 0, 'cap')")
    connection.commit()
    granted = connection.execute(
        "UPDATE execution SET sends = sends + 1 WHERE id = 'e' AND status = 'reserved' AND capability = 'cap'"
    ).rowcount
    connection.execute(
        "UPDATE execution SET status = 'settled', capability = 'dead' WHERE id = 'e' AND status = 'reserved'"
    )
    connection.commit()
    missed = connection.execute(
        "UPDATE execution SET sends = sends + 1 WHERE id = 'e' AND status = 'reserved' AND capability = 'cap'"
    ).rowcount
    assert granted == 1
    assert missed == 0
    assert POSTGRES_INTEGRATION == "pending"

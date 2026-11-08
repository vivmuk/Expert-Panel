"""Offline $5 application accounting. These tests do not call a provider.

5000000 microusd is $5 of accounting, not a provider bill. This file does not
count engagement executions. HTTP routes stay closed.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading

import pytest

from server.projectbudget import (
    APPLICATION_CEILING_MICROUSD,
    BudgetStop,
    accounted,
    activation_blockers,
    create_project,
    decide,
    mark_uncertain,
    reconcile_uncertainty,
    settle,
)
from server.spendguard import SpendClosed
from tests.test_chatjob import ONE_SHOT


def test_http_stays_closed_when_a_budget_file_and_prices_exist(monkeypatch, tmp_path):
    created = create_project(str(tmp_path / "budget.db"))
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER", "sqlite")
    monkeypatch.setenv("AI_PARTNER_SPEND_LEDGER_PATH", str(tmp_path / "budget.db"))
    monkeypatch.setenv("AI_PARTNER_CALCULATED_CEILING_MICROUSD", "5000000")
    monkeypatch.setenv("AI_PARTNER_CALCULATED_MICROUSD_VENICE_ATTEMPT", "10")
    calls = []
    monkeypatch.setattr(
        "server.venice.client.requests.Session.request",
        lambda *_a, **_k: calls.append("network") or (_ for _ in ()).throw(AssertionError("provider")),
    )
    from server import create_app

    client = create_app().test_client()
    res = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "currency_bound_unavailable"
    assert calls == []
    assert accounted(str(tmp_path / "budget.db"), created["project_id"], created["seal"])["step_rows"] == 0
    assert "no_authoritative_attempt_price" in activation_blockers()


def _open(tmp_path, name="budget.db"):
    return str(tmp_path / name), create_project(str(tmp_path / name))


def test_exact_ceiling_and_one_more_microusd_stops(tmp_path):
    path, project = _open(tmp_path)
    first = decide(path, project["project_id"], project["seal"], "step-a", "venice", APPLICATION_CEILING_MICROUSD)
    assert first["kind"] == "reserved"
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], project["seal"], "step-b", "exa", 1)
    assert exc.value.code == "over_cap"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == APPLICATION_CEILING_MICROUSD


def test_two_reservations_cannot_cross_the_ceiling(tmp_path):
    """One process and one file. This is not an external anchor or a principal registry."""
    path, project = _open(tmp_path)
    barrier = threading.Barrier(2)
    outcomes = []

    def once(step):
        barrier.wait()
        try:
            outcomes.append(decide(path, project["project_id"], project["seal"], step, "venice", 3_000_000)["kind"])
        except BudgetStop as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=once, args=(f"step-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert sorted(outcomes) == ["over_cap", "reserved"]
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 3_000_000
    assert "no_external_monotonic_anchor" in activation_blockers()
    assert "no_shared_principal_registry" in activation_blockers()


def test_step_rows_are_not_an_engagement_attempt_cap(tmp_path):
    path, project = _open(tmp_path)
    for name in ("one", "two", "three", "four"):
        assert decide(path, project["project_id"], project["seal"], name, "memory", 10)["kind"] == "reserved"
        settle(path, project["project_id"], project["seal"], name, "memory", "{\"ok\":true}")
    again = decide(path, project["project_id"], project["seal"], "one", "memory", 10)
    assert again["kind"] == "reuse"
    assert again["result_json"] == "{\"ok\":true}"
    state = accounted(path, project["project_id"], project["seal"])
    assert state["step_rows"] == 4
    assert state["reserved_microusd"] == 40
    assert state["engagement_attempts"] is None


def test_reuse_binds_service_stage_and_inputs(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "same-input", "venice", 10, stage="initial")
    settle(path, project["project_id"], project["seal"], "same-input", "venice", "{\"channel\":\"venice\"}", stage="initial")
    reused = decide(path, project["project_id"], project["seal"], "same-input", "venice", 99, stage="initial")
    assert reused["kind"] == "reuse"
    assert reused["result_json"] == "{\"channel\":\"venice\"}"
    other_service = decide(path, project["project_id"], project["seal"], "same-input", "exa", 10, stage="initial")
    assert other_service["kind"] == "reserved"
    assert "result_json" not in other_service
    other_stage = decide(path, project["project_id"], project["seal"], "same-input", "venice", 10, stage="recovery")
    assert other_stage["kind"] == "reserved"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 30


def test_uncertain_step_stops_the_project_until_reconciliation(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "call", "exa", 40)
    mark_uncertain(path, project["project_id"], project["seal"], "call", "exa")
    with pytest.raises(BudgetStop) as same:
        decide(path, project["project_id"], project["seal"], "call", "exa", 40)
    assert same.value.code == "attempt_uncertain"
    with pytest.raises(BudgetStop) as other:
        decide(path, project["project_id"], project["seal"], "next", "venice", 10)
    assert other.value.code == "project_unreconciled"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 40
    reconcile_uncertainty(path, project["project_id"], project["seal"], "call", "exa")
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 40
    assert decide(path, project["project_id"], project["seal"], "next", "venice", 10)["kind"] == "reserved"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 50


def test_missing_zero_and_unknown_service_do_not_reserve(tmp_path):
    path, project = _open(tmp_path)
    for price in (0, -1, None, True):
        with pytest.raises(BudgetStop) as exc:
            decide(path, project["project_id"], project["seal"], "x", "venice", price)
        assert exc.value.code == "price_unknown"
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], project["seal"], "x", "voice", 10)
    assert exc.value.code == "service_unknown"
    assert accounted(path, project["project_id"], project["seal"])["step_rows"] == 0


def test_wrong_seal_cannot_read_or_reset_another_project(tmp_path):
    path, project = _open(tmp_path)
    other_path, other = _open(tmp_path, "other.db")
    decide(path, project["project_id"], project["seal"], "secret", "venice", 10)
    settle(path, project["project_id"], project["seal"], "secret", "venice", "{\"owner\":\"a\"}")
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], other["seal"], "secret", "venice", 10)
    assert exc.value.code == "seal_rejected"
    with pytest.raises(BudgetStop):
        decide(path, other["project_id"], project["seal"], "secret", "venice", 10)
    assert decide(other_path, other["project_id"], other["seal"], "secret", "memory", 10)["kind"] == "reserved"
    assert accounted(path, project["project_id"], project["seal"])["step_rows"] == 1


def test_restart_reuses_the_settled_result(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "step", "venice", 25)
    settle(path, project["project_id"], project["seal"], "step", "venice", "{\"n\":1}")
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.projectbudget import decide
print(decide(os.environ["JOURNAL"], os.environ["PROJECT"], os.environ["SEAL"], "step", "venice", 25)["kind"])
"""
    env = {
        **os.environ,
        "REPO": os.getcwd(),
        "JOURNAL": path,
        "PROJECT": project["project_id"],
        "SEAL": project["seal"],
    }
    completed = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "reuse"


def test_truncation_and_replacement_do_not_mint_a_new_budget(tmp_path):
    path, project = _open(tmp_path)
    inode = os.stat(path).st_ino
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)
    os.truncate(path, 0)
    assert os.stat(path).st_ino == inode
    with pytest.raises(BudgetStop) as truncated:
        decide(path, project["project_id"], project["seal"], "step", "venice", 10)
    assert truncated.value.code == "store_unproven"
    with pytest.raises(BudgetStop):
        create_project(path)
    os.remove(path)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)
    open(path, "wb").close()
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.projectbudget import BudgetStop, decide
try:
    decide(os.environ["JOURNAL"], os.environ["PROJECT"], os.environ["SEAL"], "step", "venice", 10)
    print("RESERVED")
except BudgetStop as exc:
    print(exc.code)
"""
    env = {**os.environ, "REPO": os.getcwd(), "JOURNAL": path, "PROJECT": project["project_id"], "SEAL": project["seal"]}
    completed = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "store_unproven"


def test_synthetic_cost_report_keeps_four_amounts_apart(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "initial-inference", "venice", 100, stage="initial")
    settle(path, project["project_id"], project["seal"], "initial-inference", "venice", "{\"not\":\"in-report\"}", stage="initial")
    from server.projectbudget import record_facts, report

    record_facts(
        path,
        project["project_id"],
        project["seal"],
        "initial-inference",
        "venice",
        usage={"input_tokens": 10, "output_tokens": 2},
        pricing_snapshot={"input_microusd_per_token": 3, "output_microusd_per_token": 5},
        stage="initial",
    )
    decide(path, project["project_id"], project["seal"], "inflight-memory", "memory", 7, stage="initial")
    decide(path, project["project_id"], project["seal"], "recovery-search", "exa", 40, stage="recovery")
    mark_uncertain(path, project["project_id"], project["seal"], "recovery-search", "exa", stage="recovery")
    view = report(path, project["project_id"], project["seal"], "synthetic")
    assert view["label"] == "synthetic"
    assert view["initial"]["reserved_worst_case_microusd"] == 107
    assert view["recovery"]["reserved_worst_case_microusd"] == 40
    assert view["remaining_application_microusd"] == APPLICATION_CEILING_MICROUSD - 147
    assert view["successful_delivery_reserved_microusd"] == 100
    assert view["inflight_reserved_microusd"] == 7
    assert view["uncertain_reserved_microusd"] == 40
    assert view["failed_microusd"] is None
    assert view["providers"]["venice_inference"]["reserved_worst_case_microusd"] == 100
    assert view["providers"]["venice_hosted_exa"]["reserved_worst_case_microusd"] == 40
    assert view["providers"]["supermemory"]["reserved_worst_case_microusd"] == 7
    assert "direct_exa" not in view["providers"]
    assert view["direct_exa_invoice"] is None
    assert view["amounts"]["reserved_worst_case_microusd"] == 147
    assert view["amounts"]["calculated_microusd"] is None
    assert view["amounts"]["billed_microusd"] is None
    assert view["completeness"]["billed"] == "missing"
    assert "result" not in view["steps"][0]
    assert "seal" not in view
    dumped = json.dumps(view)
    assert "initial-inference" not in dumped
    assert "in-report" not in dumped
    inference = next(item for item in view["steps"] if item["provider"] == "venice_inference")
    assert inference["calculated_microusd"] == 10 * 3 + 2 * 5
    assert inference["billed_microusd"] is None
    with pytest.raises(BudgetStop):
        record_facts(
            path,
            project["project_id"],
            project["seal"],
            "initial-inference",
            "venice",
            usage={"prompt": 1},
            stage="initial",
        )


def test_two_price_bases_are_not_added(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "mixed", "venice", 10)
    from server.projectbudget import record_facts, report

    record_facts(
        path,
        project["project_id"],
        project["seal"],
        "mixed",
        "venice",
        usage={"input_tokens": 1, "output_tokens": 1, "request_count": 1},
        pricing_snapshot={"input_microusd_per_token": 2, "output_microusd_per_token": 2, "per_request_microusd": 9},
        billed_microusd=4,
    )
    view = report(path, project["project_id"], project["seal"], "synthetic")
    mixed = view["steps"][0]
    assert mixed["calculated_microusd"] is None
    assert mixed["billed_microusd"] == 4
    assert view["amounts"]["billed_microusd"] == 4
    assert view["amounts"]["calculated_microusd"] is None


def test_shared_partner_key_has_no_cost_route(monkeypatch):
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "static-test-key")
    from server import create_app

    app = create_app()
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    assert not any("cost" in rule or "budget" in rule for rule in rules)
    res = app.test_client().get("/api/project-cost", headers={"Authorization": "Bearer static-test-key"})
    assert res.status_code == 404


def test_memory_path_is_not_a_budget(tmp_path):
    with pytest.raises(BudgetStop) as exc:
        create_project(":memory:")
    assert exc.value.code == "store_unproven"
    with pytest.raises(SpendClosed):
        from server.spendguard import refuse_paid

        refuse_paid()


def _checkpoint(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def test_facts_stay_when_a_later_write_omits_them(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "priced", "venice", 10)
    from server.projectbudget import record_facts, report

    record_facts(
        path,
        project["project_id"],
        project["seal"],
        "priced",
        "venice",
        usage={"input_tokens": 10, "output_tokens": 1},
    )
    record_facts(
        path,
        project["project_id"],
        project["seal"],
        "priced",
        "venice",
        billed_microusd=0,
    )
    with pytest.raises(BudgetStop) as conflict:
        record_facts(
            path,
            project["project_id"],
            project["seal"],
            "priced",
            "venice",
            usage={"input_tokens": 1, "output_tokens": 1},
        )
    assert conflict.value.code == "fact_conflict"
    step = report(path, project["project_id"], project["seal"], "synthetic")["steps"][0]
    assert step["provider_reported_usage"] == {"input_tokens": 10, "output_tokens": 1}
    assert step["billed_microusd"] == 0
    assert step["pricing_snapshot"] is None
    assert step["calculated_microusd"] is None


def test_report_identifier_does_not_echo_caller_text(tmp_path):
    path, project = _open(tmp_path)
    secret = "user@example.com sk-secret ?q=token"
    decide(path, project["project_id"], project["seal"], secret, "memory", 10)
    from server.projectbudget import report

    view = report(path, project["project_id"], project["seal"], "ledger")
    assert secret not in json.dumps(view)
    assert view["steps"][0]["step_id"] != secret
    assert view["runtime_enforcement"] is False
    assert view["engagement_attempts"] is None
    assert view["engagement_attempt_cap_enforced"] is False
    assert "engagement_attempt_not_counted" in view["gaps"]


def test_reservation_does_not_multiply_hidden_provider_retries(tmp_path):
    from server.venice.client import MAX_ATTEMPTS

    path, project = _open(tmp_path)
    decision = decide(path, project["project_id"], project["seal"], "one-call", "venice", 10)
    assert MAX_ATTEMPTS > 1
    assert decision["reserved_microusd"] == 10
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 10


def test_restored_valid_snapshot_spends_the_old_remainder_unsolved(tmp_path):
    """UNSOLVED. An earlier valid copy is accepted. This expects the hole."""
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "first", "venice", 3_000_000)
    settle(path, project["project_id"], project["seal"], "first", "venice", "{\"ok\":true}")
    _checkpoint(path)
    snapshot = open(path, "rb").read()
    decide(path, project["project_id"], project["seal"], "second", "venice", 1_000_000)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)
    with open(path, "wb") as handle:
        handle.write(snapshot)
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.projectbudget import accounted, decide
decision = decide(os.environ["JOURNAL"], os.environ["PROJECT"], os.environ["SEAL"], "third", "venice", 2000000)
state = accounted(os.environ["JOURNAL"], os.environ["PROJECT"], os.environ["SEAL"])
print(decision["kind"])
print(state["reserved_microusd"])
print(state["step_rows"])
"""
    env = {**os.environ, "REPO": os.getcwd(), "JOURNAL": path, "PROJECT": project["project_id"], "SEAL": project["seal"]}
    completed = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
    assert completed.returncode == 0, completed.stderr
    kind, reserved, rows = completed.stdout.splitlines()
    assert kind == "reserved"
    assert reserved == "5000000"
    assert rows == "2"


def test_copying_the_file_forks_the_budget_unsolved(tmp_path):
    """UNSOLVED. A byte copy at a new path spends again. No new project is created for the copy."""
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "first", "venice", 100)
    _checkpoint(path)
    fork = str(tmp_path / "fork.db")
    shutil.copy(path, fork)
    assert accounted(fork, project["project_id"], project["seal"])["reserved_microusd"] == 100
    assert decide(path, project["project_id"], project["seal"], "more", "venice", 4_999_900)["kind"] == "reserved"
    assert decide(fork, project["project_id"], project["seal"], "more-fork", "venice", 4_999_900)["kind"] == "reserved"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == APPLICATION_CEILING_MICROUSD
    assert accounted(fork, project["project_id"], project["seal"])["reserved_microusd"] == APPLICATION_CEILING_MICROUSD


def test_deleting_the_file_mints_another_budget_unsolved(tmp_path):
    """UNSOLVED. No shared principal registry. A new file is another $5."""
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "first", "venice", 100)
    os.remove(path)
    for suffix in ("-wal", "-shm"):
        extra = path + suffix
        if os.path.exists(extra):
            os.remove(extra)
    minted = create_project(path)
    assert minted["project_id"] != project["project_id"]
    assert decide(path, minted["project_id"], minted["seal"], "again", "venice", APPLICATION_CEILING_MICROUSD)["kind"] == "reserved"

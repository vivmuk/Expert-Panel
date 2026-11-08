"""$5 application accounting. These tests do not call a provider.

5000000 microusd is $5 of accounting, not a provider bill. HTTP routes stay
closed even when this file exists and calculated prices are set.
"""
import os
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
    assert accounted(str(tmp_path / "budget.db"), created["project_id"], created["seal"])["attempts"] == 0
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


def test_three_attempts_then_stop_and_a_duplicate_does_not_consume_another(tmp_path):
    path, project = _open(tmp_path)
    for name in ("one", "two", "three"):
        assert decide(path, project["project_id"], project["seal"], name, "memory", 10)["kind"] == "reserved"
        settle(path, project["project_id"], project["seal"], name, "{\"ok\":true}")
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], project["seal"], "four", "venice", 10)
    assert exc.value.code == "attempts_exhausted"
    again = decide(path, project["project_id"], project["seal"], "one", "memory", 10)
    assert again["kind"] == "reuse"
    assert again["result_json"] == "{\"ok\":true}"
    assert accounted(path, project["project_id"], project["seal"])["attempts"] == 3


def test_uncertain_attempt_stops_and_keeps_the_reservation(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "call", "exa", 40)
    mark_uncertain(path, project["project_id"], project["seal"], "call")
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], project["seal"], "call", "exa", 40)
    assert exc.value.code == "attempt_uncertain"
    assert accounted(path, project["project_id"], project["seal"])["reserved_microusd"] == 40


def test_missing_zero_and_unknown_service_do_not_reserve(tmp_path):
    path, project = _open(tmp_path)
    for price in (0, -1, None, True):
        with pytest.raises(BudgetStop) as exc:
            decide(path, project["project_id"], project["seal"], "x", "venice", price)
        assert exc.value.code == "price_unknown"
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], project["seal"], "x", "voice", 10)
    assert exc.value.code == "service_unknown"
    assert accounted(path, project["project_id"], project["seal"])["attempts"] == 0


def test_wrong_seal_cannot_read_or_reset_another_project(tmp_path):
    path, project = _open(tmp_path)
    other_path, other = _open(tmp_path, "other.db")
    decide(path, project["project_id"], project["seal"], "secret", "venice", 10)
    settle(path, project["project_id"], project["seal"], "secret", "{\"owner\":\"a\"}")
    with pytest.raises(BudgetStop) as exc:
        decide(path, project["project_id"], other["seal"], "secret", "venice", 10)
    assert exc.value.code == "seal_rejected"
    with pytest.raises(BudgetStop):
        decide(path, other["project_id"], project["seal"], "secret", "venice", 10)
    assert decide(other_path, other["project_id"], other["seal"], "secret", "memory", 10)["kind"] == "reserved"
    assert accounted(path, project["project_id"], project["seal"])["attempts"] == 1


def test_restart_reuses_the_settled_result(tmp_path):
    path, project = _open(tmp_path)
    decide(path, project["project_id"], project["seal"], "step", "venice", 25)
    settle(path, project["project_id"], project["seal"], "step", "{\"n\":1}")
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


def test_memory_path_is_not_a_budget(tmp_path):
    with pytest.raises(BudgetStop) as exc:
        create_project(":memory:")
    assert exc.value.code == "store_unproven"
    with pytest.raises(SpendClosed):
        from server.spendguard import refuse_paid

        refuse_paid()

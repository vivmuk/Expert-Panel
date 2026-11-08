"""Disposable Postgres proof of the exposure contract. Not a production cap.

The suite reads EXPOSURE_TEST_DATABASE_URL only. It does not read DATABASE_URL.
The host must be local and the database name must be exposure_test.
"""
import os
import socket
import subprocess
import threading
from urllib.parse import urlsplit

import pytest

from server.api.branding import _generate_slot
from server.api.chat import complete_with_venice
from server.api.voice import _planned, _transcribe
from server.chatmemory import recall, remember
from server.exa_search import exa_search
from server.exposure import (
    APPLICATION_CEILING_MICROUSD,
    MAX_ENGAGEMENT_ATTEMPTS,
    VENICE_UPSTREAM_TRIES,
    describe_venice,
)
from server.pg_authority import PostgresAuthority, drop_schema, install_schema
from server.spendguard import SpendClosed
from tests.test_chatjob import ONE_SHOT
from tests.test_exposure import Recording, _req, _requests, _schedule, _work

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_PG_BIN = "/usr/lib/postgresql/16/bin"


def assert_throwaway(url):
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError("missing explicit disposable Postgres URL")
    if os.environ.get("DATABASE_URL") and url == os.environ.get("DATABASE_URL") and "railway" in url.lower():
        raise RuntimeError("refusing Railway DATABASE_URL")
    parts = urlsplit(url.strip())
    if parts.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("unsupported scheme")
    host = (parts.hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        raise RuntimeError("refusing non-local Postgres endpoint")
    if parts.path.lstrip("/") != "exposure_test":
        raise RuntimeError("refusing database that is not exposure_test")
    return url.strip()


def resolve_test_dsn():
    explicit = os.environ.get("EXPOSURE_TEST_DATABASE_URL", "").strip()
    required = os.environ.get("EXPOSURE_PG_REQUIRED") == "1"
    if not explicit:
        if required:
            pytest.fail("EXPOSURE_PG_REQUIRED is set and EXPOSURE_TEST_DATABASE_URL is missing")
        pytest.skip("EXPOSURE_TEST_DATABASE_URL is not set")
    return assert_throwaway(explicit)


@pytest.fixture
def authority():
    dsn = resolve_test_dsn()
    schema = "exp_" + __import__("secrets").token_hex(8)
    install_schema(dsn, schema)
    store = PostgresAuthority(dsn, _schedule(), schema)
    try:
        yield store
    finally:
        drop_schema(dsn, schema)


def test_explicit_database_url_is_required_when_the_pg_job_runs(monkeypatch):
    monkeypatch.setenv("EXPOSURE_PG_REQUIRED", "1")
    monkeypatch.delenv("EXPOSURE_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://exposure@127.0.0.1:1/exposure_test")
    with pytest.raises(pytest.fail.Exception):
        resolve_test_dsn()


def test_nonlocal_and_wrong_database_are_refused():
    with pytest.raises(RuntimeError):
        assert_throwaway("postgresql://exposure@db.railway.internal/exposure_test")
    with pytest.raises(RuntimeError):
        assert_throwaway("postgresql://exposure@127.0.0.1/postgres")


def test_two_connections_cannot_cross_the_ceiling(authority):
    project = authority.provision_project("pilot-engagement")
    other = PostgresAuthority(authority._dsn, _schedule(), authority._schema)
    schedule = [{"service": "memory", "model": "offline", "max_input_bytes": 2000, "max_output_tokens": 200,
                 "max_duration_seconds": 60, "max_items": 4, "upstream_tries": 1, "repair_tries": 0,
                 "unit_microusd": 3_000_000, "provenance": "synthetic"}]
    left = PostgresAuthority(authority._dsn, schedule, authority._schema)
    right = PostgresAuthority(authority._dsn, schedule, authority._schema)
    barrier = threading.Barrier(2)
    outcomes = []

    def once(store, payload):
        barrier.wait()
        try:
            outcomes.append(store.begin(project["project_id"], project["seal"], [_req("memory", payload)])["kind"])
        except Exception as exc:
            outcomes.append(getattr(exc, "code", type(exc).__name__))

    threads = [
        threading.Thread(target=once, args=(left, "side-a")),
        threading.Thread(target=once, args=(right, "side-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(outcomes) == ["over_cap", "reserved"]
    assert other.accounted(project["project_id"], project["seal"])["reserved_microusd"] == 3_000_000
    assert other.accounted(project["project_id"], project["seal"])["engagement_attempts"] == 1


def test_fourth_execution_replay_and_duration(authority):
    project = authority.provision_project("pilot-engagement")
    transport = Recording(authority, project)

    def work(text):
        def inner():
            complete_with_venice("offline", [{"role": "user", "content": text}], {}, 8)
            return "stored"

        return inner

    first = None
    for index in range(MAX_ENGAGEMENT_ATTEMPTS):
        text = f"attempt-{index}"
        done = run_pg(authority, project, [_req("venice", text)], transport, work(text))
        assert done["kind"] == "settled"
        first = done if index == 0 else first
    again = run_pg(authority, project, [_req("venice", "attempt-0")], Recording(authority, project), work("attempt-0"), first["execution_id"])
    assert again["kind"] == "reuse"
    assert again["result"] == "stored"
    with pytest.raises(Exception) as mismatch:
        run_pg(authority, project, [_req("venice", "changed")], Recording(authority, project), work("changed"), first["execution_id"])
    assert mismatch.value.code == "request_mismatch"
    quiet = Recording(authority, project)
    with pytest.raises(Exception) as exhausted:
        run_pg(authority, project, [_req("venice", "attempt-extra")], quiet, work("attempt-extra"))
    assert exhausted.value.code == "attempts_exhausted"
    assert quiet.calls == []
    body = [{"role": "user", "content": "timed"}]
    with pytest.raises(Exception) as too_long:
        authority.begin(project["project_id"], project["seal"], [describe_venice("offline", body, {}, 8, duration_seconds=61)])
    assert too_long.value.code == "envelope_rejected"


def run_pg(authority, project, requests, transport, work, execution_id=None):
    from server.exposure import run_execution

    return run_execution(
        authority, project["project_id"], project["seal"], requests, transport, work, execution_id=execution_id
    )


def test_one_slot_and_sibling_settlement(authority):
    project = authority.provision_project("pilot-engagement")
    slot = _req("venice", "slot")
    opened = authority.begin(project["project_id"], project["seal"], [slot])
    barrier = threading.Barrier(2)
    outcomes = []

    def once():
        barrier.wait()
        try:
            authority.authorize_send(project["project_id"], project["seal"], opened["execution_id"], opened["capability"], slot)
            outcomes.append("sent")
        except SpendClosed:
            outcomes.append("stopped")

    threads = [threading.Thread(target=once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(outcomes) == ["sent", "stopped"]
    first = _req("venice", "first")
    second = _req("venice", "second")
    opened_a = authority.begin(project["project_id"], project["seal"], [first])
    opened_b = authority.begin(project["project_id"], project["seal"], [second])
    authority.authorize_send(project["project_id"], project["seal"], opened_b["execution_id"], opened_b["capability"], second)
    authority.mark_uncertain(project["project_id"], project["seal"], opened_a["execution_id"])
    assert authority.settle(project["project_id"], project["seal"], opened_b["execution_id"], "success-token") == "uncertain"
    state = authority.accounted(project["project_id"], project["seal"])
    assert state["engagement_attempts"] == 3
    with pytest.raises(SpendClosed):
        authority.authorize_send(project["project_id"], project["seal"], opened_b["execution_id"], opened_b["capability"], second)


def test_void_retry_and_a_second_process(authority):
    project = authority.provision_project("pilot-engagement")
    request = [_req("voice", "same")]
    opened = authority.begin(project["project_id"], project["seal"], request)
    authority.void_unsent(project["project_id"], project["seal"], opened["execution_id"])
    with pytest.raises(Exception) as old:
        authority.begin(project["project_id"], project["seal"], request, execution_id=opened["execution_id"])
    assert old.value.code == "execution_rejected"
    fresh = authority.begin(project["project_id"], project["seal"], request)
    assert fresh["execution_id"] != opened["execution_id"]
    assert fresh["kind"] == "reserved"
    child = """
import os, sys
sys.path.insert(0, os.environ["REPO"])
from server.exposure import ExposureStop
from server.pg_authority import PostgresAuthority
from tests.test_exposure import _req, _schedule
store = PostgresAuthority(os.environ["EXPOSURE_TEST_DATABASE_URL"], _schedule(), os.environ["SCHEMA"])
try:
    kind = store.begin(os.environ["PROJECT"], os.environ["SEAL"], [_req("voice", "same")])["kind"]
    print(kind)
except ExposureStop as exc:
    print(exc.code)
"""
    env = {
        **os.environ,
        "REPO": "/agent/repos/Expert-Panel",
        "PYTHONPATH": "/tmp/ai-partner-pydeps",
        "SCHEMA": authority._schema,
        "PROJECT": project["project_id"],
        "SEAL": project["seal"],
    }
    completed = subprocess.run(
        ["/tmp/ai-partner-venv/bin/python", "-c", child],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "attempt_uncertain"


def test_postmaster_stop_start_keeps_the_committed_row(tmp_path):
    data = tmp_path / "data"
    log = tmp_path / "server.log"
    initdb = f"{_PG_BIN}/initdb"
    pg_ctl = f"{_PG_BIN}/pg_ctl"
    createdb = f"{_PG_BIN}/createdb"
    if not os.path.exists(pg_ctl):
        if os.environ.get("EXPOSURE_PG_REQUIRED") == "1":
            pytest.fail("pg_ctl is missing; stop/start proof cannot be skipped")
        pytest.skip("pg_ctl is missing")
    subprocess.check_call(
        [initdb, "-D", str(data), "-U", "exposure", "--auth=trust", "--encoding=UTF8", "--locale=C"],
        stdout=subprocess.DEVNULL,
    )
    with open(data / "postgresql.conf", "a", encoding="utf-8") as handle:
        handle.write("\nlisten_addresses = '127.0.0.1'\nport = 55433\nunix_socket_directories = '/tmp'\n")
    with open(data / "pg_hba.conf", "w", encoding="utf-8") as handle:
        handle.write("local all exposure trust\nhost all exposure 127.0.0.1/32 trust\nhost all exposure ::1/128 trust\n")
    subprocess.check_call([pg_ctl, "-D", str(data), "-l", str(log), "start", "-w"])
    try:
        subprocess.check_call([createdb, "-h", "127.0.0.1", "-p", "55433", "-U", "exposure", "exposure_test"])
        dsn = assert_throwaway("postgresql://exposure@127.0.0.1:55433/exposure_test")
        schema = "exp_" + __import__("secrets").token_hex(8)
        install_schema(dsn, schema)
        store = PostgresAuthority(dsn, _schedule(), schema)
        project = store.provision_project("pilot-engagement")
        opened = store.begin(project["project_id"], project["seal"], [_req("venice", "restart")])
        subprocess.check_call([pg_ctl, "-D", str(data), "stop", "-m", "fast", "-w"])
        subprocess.check_call([pg_ctl, "-D", str(data), "-l", str(log), "start", "-w"])
        revived = PostgresAuthority(dsn, _schedule(), schema)
        state = revived.accounted(project["project_id"], project["seal"])
        assert state["engagement_attempts"] == 1
        assert state["reserved_microusd"] == opened["reserved_microusd"]
        drop_schema(dsn, schema)
    finally:
        subprocess.call([pg_ctl, "-D", str(data), "stop", "-m", "fast", "-w"])


def test_operator_project_is_idempotent_and_the_report_keeps_amounts_apart(authority):
    first = authority.provision_project("pilot-engagement")
    second = authority.provision_project("pilot-engagement")
    assert second["project_id"] == first["project_id"]
    assert second["seal"] == first["seal"]
    with pytest.raises(Exception) as email:
        authority.provision_project("person@example.com")
    assert email.value.code == "project_rejected"
    with pytest.raises(Exception) as chat:
        authority.provision_project("chat-abc")
    assert chat.value.code == "project_rejected"
    with pytest.raises(Exception) as unknown:
        authority.begin("not-provisioned", first["seal"], [_req("venice", "x")])
    assert unknown.value.code == "project_rejected"
    done = authority.begin(first["project_id"], first["seal"], [_req("venice", "payload-token-9f3c")])
    authority.settle(first["project_id"], first["seal"], done["execution_id"], "hidden-result")
    view = authority.report(first["project_id"], first["seal"])
    assert view["production_cap"] is False
    assert view["price_provenance"] == "synthetic"
    assert view["amounts"]["reserved_worst_case_microusd"] == done["reserved_microusd"]
    assert view["amounts"]["estimated_microusd"] is None
    assert view["amounts"]["provider_reported_usage"] is None
    assert view["amounts"]["billed_microusd"] is None
    assert view["executions"][0]["billed_microusd"] is None
    dumped = __import__("json").dumps(view)
    assert "hidden-result" not in dumped
    assert "payload-token-9f3c" not in dumped
    with pytest.raises(Exception) as wrong:
        authority.report(first["project_id"], "wrong-seal")
    assert wrong.value.code == "seal_rejected"


def test_helpers_use_the_postgres_authority_and_http_does_not(authority, monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "offline-memory")
    monkeypatch.setenv("DATABASE_URL", authority._dsn)
    project = authority.provision_project("pilot-engagement")
    transport = Recording(authority, project)
    done = run_pg(authority, project, _requests("one"), transport, _work)
    assert done["kind"] == "settled"
    assert transport.calls == ["venice", "exa", "memory", "memory-write", "voice", "image"]
    assert transport.payloads[0] == _requests("one")[0]["payload"]
    blob = b"RIFF\x00\xffTRANSCRIBE-MARKER"
    audio = describe_voice_blob(blob)
    heard = Recording(authority, project)

    def transcribe():
        from server.api.voice import _transcribe

        _transcribe(blob, "audio/webm")
        return "ok"

    voice_done = run_pg(authority, project, [audio], heard, transcribe)
    assert voice_done["kind"] == "settled"
    assert heard.payloads == [audio["payload"]]
    dumped = __import__("json").dumps(authority.report(project["project_id"], project["seal"]))
    assert "TRANSCRIBE-MARKER" not in dumped
    quiet = Recording(authority, project)

    def wrong():
        complete_with_venice("offline", [{"role": "user", "content": "changed"}], {}, 8)
        return "ok"

    with pytest.raises(SpendClosed):
        run_pg(authority, project, [describe_venice("offline", [{"role": "user", "content": "declared"}], {}, 8)], quiet, wrong)
    assert quiet.calls == []
    before = _schemas(authority._dsn)
    monkeypatch.delenv("VERCEL", raising=False)
    from server import create_app

    client = create_app().test_client()
    response = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "currency_bound_unavailable"
    assert _schemas(authority._dsn) == before
    rules = [rule.rule for rule in client.application.url_map.iter_rules()]
    assert not any("cost" in rule or "budget" in rule or "exposure" in rule for rule in rules)


def describe_voice_blob(blob):
    from server.exposure import describe_voice

    return describe_voice("transcribe", {"blob": blob, "mime": "audio/webm"})


def _schemas(dsn):
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'exp_%' ORDER BY nspname"
        ).fetchall()
    return [row[0] for row in rows]

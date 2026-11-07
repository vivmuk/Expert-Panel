"""Partner-key gate for the legacy panel store, runs, and brand generation.

A valid key can read and change the one shared SQLite store. It does not get a
private store. These tests double start_run and brand generation so Venice is
never called.
"""
import socket

import pytest

from server.config import Config
from server.pipeline.events import REGISTRY

KEY = "partner-test-key"
OTHER = "other-partner-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
OTHER_AUTH = {"Authorization": f"Bearer {OTHER}"}


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AI_PARTNER_API_KEYS", f"{KEY},{OTHER}")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    started = []

    def start_run(payload):
        started.append(payload)
        run = REGISTRY.create("deep_dive", 1)
        return run, 1, {"totalCostUsd": 0, "panelSize": 20, "stages": []}

    monkeypatch.setattr("server.api.runs.start_run", start_run)
    brand = []

    def ensure(*args, **kwargs):
        brand.append((args, kwargs))
        return []

    monkeypatch.setattr("server.api.branding._ensure_missing_async", ensure)

    def catalog():
        raise AssertionError("brand generation reached the model catalog")

    monkeypatch.setattr("server.api.branding.get_catalog", catalog)
    from server import create_app

    flask_app = create_app()
    flask_app.config["started"] = started
    flask_app.config["brand"] = brand
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_tests_cannot_open_an_external_socket():
    with pytest.raises(RuntimeError, match="outbound connection blocked"):
        socket.create_connection(("example.com", 443), timeout=1)


def test_runs_reject_a_missing_or_wrong_key_before_start_or_lookup(client, app, monkeypatch):
    hits = []
    real_get = REGISTRY.get

    def wrapped(run_id):
        hits.append(run_id)
        return real_get(run_id)

    monkeypatch.setattr(REGISTRY, "get", wrapped)
    missing = client.post("/api/runs", json={"input": {"problem": "Launch a clinic."}})
    wrong = client.post("/api/runs", json={"input": {"problem": "Launch a clinic."}}, headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.get_json()["error"]["code"] == "unauthorized"
    assert app.config["started"] == []
    for path, method in (
        ("/api/runs/r_missing", "get"),
        ("/api/runs/r_missing/events", "get"),
        ("/api/runs/r_missing/answers", "post"),
        ("/api/runs/r_missing/cancel", "post"),
    ):
        denied = getattr(client, method)(path, json={})
        assert denied.status_code == 401, path
    assert hits == []


def test_runs_with_a_partner_key_use_the_double_and_not_the_provider(client, app):
    created = client.post(
        "/api/runs",
        json={"mode": "deep_dive", "input": {"problem": "Launch a clinic."}},
        headers=AUTH,
    )
    assert created.status_code == 202
    assert app.config["started"][0]["input"]["problem"] == "Launch a clinic."
    body = created.get_json()
    fetched = client.get(f"/api/runs/{body['runId']}", headers=AUTH)
    assert fetched.status_code == 200
    assert fetched.get_json()["runId"] == body["runId"]
    answered = client.post(f"/api/runs/{body['runId']}/answers", json={"answers": {"q": "yes"}}, headers=AUTH)
    assert answered.status_code == 200
    cancelled = client.post(f"/api/runs/{body['runId']}/cancel", headers=AUTH)
    assert cancelled.status_code == 200
    missing = client.get("/api/runs/r_missing/events", headers=AUTH)
    assert missing.status_code == 404
    bare = client.get(f"/api/runs/{body['runId']}")
    assert bare.status_code == 401


def test_store_requires_a_key_and_keys_share_one_store(client):
    from server.db import engagements as store

    engagement_id = store.create_engagement("deep_dive", "Shared clinic launch")
    store.add_revision(engagement_id, {"input": {"problem": "Shared clinic launch"}}, note="created")
    missing = client.get("/api/engagements")
    wrong = client.get("/api/engagements", headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert "Shared clinic launch" not in missing.get_data(as_text=True)
    first = client.get("/api/engagements", headers=AUTH)
    second = client.get("/api/engagements", headers=OTHER_AUTH)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()[0]["id"] == second.get_json()[0]["id"] == engagement_id
    detail = client.get(f"/api/engagements/{engagement_id}", headers=OTHER_AUTH)
    assert detail.status_code == 200
    assert detail.get_json()["title"] == "Shared clinic launch"
    revision = client.get(f"/api/engagements/{engagement_id}/revisions/1", headers=AUTH)
    assert revision.status_code == 200
    renamed = client.patch(f"/api/engagements/{engagement_id}", json={"title": "Renamed by the other key"}, headers=OTHER_AUTH)
    assert renamed.status_code == 200
    assert client.get(f"/api/engagements/{engagement_id}", headers=AUTH).get_json()["title"] == "Renamed by the other key"
    blocked = client.delete(f"/api/engagements/{engagement_id}")
    assert blocked.status_code == 401
    assert client.get(f"/api/engagements/{engagement_id}", headers=AUTH).status_code == 200
    assert client.delete(f"/api/engagements/{engagement_id}", headers=AUTH).status_code == 200
    assert client.get(f"/api/engagements/{engagement_id}", headers=OTHER_AUTH).status_code == 404


def test_pagination_rejects_bad_types_and_keeps_the_existing_upper_clamp(client, monkeypatch):
    seen = {}

    def capture(mode=None, query=None, limit=50, offset=0):
        seen["limit"] = limit
        seen["offset"] = offset
        return []

    monkeypatch.setattr("server.api.engagements.store.list_engagements", capture)
    bad = client.get("/api/engagements?limit=foo", headers=AUTH)
    assert bad.status_code == 400
    assert bad.get_json()["error"]["code"] == "bad_request"
    assert "Traceback" not in bad.get_data(as_text=True)
    assert seen == {}
    for query in ("limit=-1", "limit=0", "offset=-1", "offset=1000001", "limit=1.5", "offset="):
        res = client.get("/api/engagements?" + query, headers=AUTH)
        assert res.status_code == 400, query
    assert client.get("/api/engagements?limit=foo").status_code == 401
    ok = client.get("/api/engagements?limit=201&offset=0", headers=AUTH)
    assert ok.status_code == 200
    assert seen == {"limit": 200, "offset": 0}
    client.get("/api/engagements?limit=1&offset=3", headers=AUTH)
    assert seen == {"limit": 1, "offset": 3}


def test_brand_writes_require_a_key_before_generation(client, app):
    missing = client.post("/api/branding/ensure")
    wrong = client.post("/api/branding/generate", json={"slot": "hero"}, headers={"Authorization": "Bearer nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert app.config["brand"] == []
    ensured = client.post("/api/branding/ensure", headers=AUTH)
    assert ensured.status_code == 200
    assert ensured.get_json()["started"] == []
    generated = client.post("/api/branding/generate", json={"slot": "hero"}, headers=OTHER_AUTH)
    assert generated.status_code == 200
    assert app.config["brand"][-1][0][0] == ["hero"]
    assets = client.get("/api/branding/assets")
    assert assets.status_code == 200
    assert "hero" in assets.get_json()


def test_public_chat_stays_open_and_vercel_still_has_no_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AI_PARTNER_API_KEYS", KEY)
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    http = create_app().test_client()
    assert http.get("/chat").status_code == 200
    assert b"Your first engagement is free" in http.get("/chat").data
    denied = http.get("/api/engagements")
    assert denied.status_code == 401
    blocked = http.get("/api/engagements", headers=AUTH)
    assert blocked.status_code == 503
    assert blocked.get_json()["error"]["code"] == "no_store"
    assert not (tmp_path / "engagements.db").exists()

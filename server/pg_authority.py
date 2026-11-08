"""Postgres stand-in for the exposure contract. Not a production cap.

Tests pass an explicit throwaway DSN. This module does not read DATABASE_URL
and does not arm HTTP. Synthetic schedule rows only. A restored database is
not detected; sends stay an operator decision outside this file.
"""
import json
import re
import secrets
from urllib.parse import urlsplit

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

from .exposure import (
    APPLICATION_CEILING_MICROUSD,
    MAX_ENGAGEMENT_ATTEMPTS,
    ExposureAuthority,
    ExposureStop,
    _actual,
    _match_line,
    quote,
)
from .spendguard import SpendClosed

SCHEMA_SQL = """
CREATE TABLE principal (
    id text PRIMARY KEY,
    label text NOT NULL UNIQUE
);
CREATE TABLE project (
    id text PRIMARY KEY,
    principal_id text NOT NULL UNIQUE REFERENCES principal (id),
    seal text NOT NULL,
    ceiling_microusd bigint NOT NULL
);
CREATE TABLE execution (
    id text PRIMARY KEY,
    project_id text NOT NULL REFERENCES project (id),
    report_id text NOT NULL,
    capability text NOT NULL,
    fingerprint text NOT NULL,
    status text NOT NULL,
    reconciled boolean NOT NULL,
    reserved_microusd bigint NOT NULL,
    snapshot jsonb NOT NULL,
    used integer[] NOT NULL,
    sends integer NOT NULL,
    result text
);
CREATE UNIQUE INDEX execution_live_fingerprint
    ON execution (project_id, fingerprint)
    WHERE status <> 'void';
"""


def throwaway_params(url):
    """Local exposure_test only. Query and service overrides are rejected before connect."""
    if not isinstance(url, str) or not url.strip() or "://" not in url:
        raise RuntimeError("missing explicit disposable Postgres URL")
    parts = urlsplit(url.strip())
    if parts.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("unsupported scheme")
    if parts.query or parts.fragment:
        raise RuntimeError("refusing connection URI parameters")
    host = (parts.hostname or "").lower().strip("[]")
    if host not in _LOCAL_HOSTS:
        raise RuntimeError("refusing non-local Postgres endpoint")
    if parts.port is None:
        raise RuntimeError("refusing implicit port")
    if parts.path.lstrip("/") != "exposure_test":
        raise RuntimeError("refusing database that is not exposure_test")
    if not parts.username:
        raise RuntimeError("refusing implicit user")
    params = {
        "host": "127.0.0.1" if host == "localhost" else host,
        "port": parts.port,
        "dbname": "exposure_test",
        "user": parts.username,
    }
    if parts.password is not None:
        params["password"] = parts.password
    return params


def connect_throwaway(url, **kwargs):
    return psycopg.connect(**throwaway_params(url), **kwargs)


def install_schema(dsn, schema):
    if not re.fullmatch(r"exp_[a-z0-9]{16}", schema):
        raise RuntimeError("refusing schema name")
    throwaway_params(dsn)
    with connect_throwaway(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        connection.execute(SCHEMA_SQL)


def drop_schema(dsn, schema):
    if not re.fullmatch(r"exp_[a-z0-9]{16}", schema):
        raise RuntimeError("refusing schema name")
    throwaway_params(dsn)
    with connect_throwaway(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


class PostgresAuthority(ExposureAuthority):
    def __init__(self, dsn, schedule, schema):
        self._dsn = dsn
        self._schedule = schedule
        self._schema = schema

    def _connect(self):
        connection = connect_throwaway(self._dsn, autocommit=False, row_factory=dict_row)
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self._schema)))
        return connection

    def provision_project(self, label):
        if not isinstance(label, str) or not label or "@" in label or label.startswith("chat"):
            raise ExposureStop("project_rejected")
        with self._connect() as connection:
            try:
                row = connection.execute(
                    """SELECT project.id AS project_id, project.seal
                       FROM principal
                       JOIN project ON project.principal_id = principal.id
                       WHERE principal.label = %s
                       FOR UPDATE OF project""",
                    (label,),
                ).fetchone()
                if row is not None:
                    connection.commit()
                    return {"project_id": row["project_id"], "seal": row["seal"]}
                principal_id = secrets.token_hex(16)
                project_id = secrets.token_hex(16)
                seal = secrets.token_urlsafe(32)
                connection.execute(
                    "INSERT INTO principal (id, label) VALUES (%s, %s)",
                    (principal_id, label),
                )
                connection.execute(
                    """INSERT INTO project (id, principal_id, seal, ceiling_microusd)
                       VALUES (%s, %s, %s, %s)""",
                    (project_id, principal_id, seal, APPLICATION_CEILING_MICROUSD),
                )
                connection.commit()
                return {"project_id": project_id, "seal": seal}
            except psycopg.errors.UniqueViolation:
                connection.rollback()
                row = connection.execute(
                    """SELECT project.id AS project_id, project.seal
                       FROM principal
                       JOIN project ON project.principal_id = principal.id
                       WHERE principal.label = %s""",
                    (label,),
                ).fetchone()
                connection.rollback()
                if row is None:
                    raise ExposureStop("project_rejected")
                return {"project_id": row["project_id"], "seal": row["seal"]}
            except Exception:
                connection.rollback()
                raise

    def _lock_project(self, connection, project_id, seal):
        row = connection.execute(
            "SELECT id, seal, ceiling_microusd FROM project WHERE id = %s FOR UPDATE",
            (project_id,),
        ).fetchone()
        if row is None:
            raise ExposureStop("project_rejected")
        if not isinstance(seal, str) or row["seal"] != seal:
            raise ExposureStop("seal_rejected")
        return row

    def _rows(self, connection, project_id):
        rows = connection.execute(
            """SELECT id, report_id, capability, fingerprint, status, reconciled,
                      reserved_microusd, snapshot, used, sends, result
               FROM execution WHERE project_id = %s""",
            (project_id,),
        ).fetchall()
        for row in rows:
            if isinstance(row["snapshot"], str):
                row["snapshot"] = json.loads(row["snapshot"])
            row["used"] = list(row["used"] or [])
        return rows

    def begin(self, project_id, seal, requests, execution_id=None):
        reserved, snapshot, fingerprint = quote(self._schedule, requests)
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                rows = self._rows(connection, project_id)
                if execution_id is not None:
                    if not isinstance(execution_id, str) or not execution_id:
                        raise ExposureStop("execution_rejected")
                    named = next((item for item in rows if item["id"] == execution_id), None)
                    if named is None or named["status"] == "void":
                        raise ExposureStop("execution_rejected")
                    if named["fingerprint"] != fingerprint:
                        raise ExposureStop("request_mismatch")
                found = next(
                    (item for item in rows if item["fingerprint"] == fingerprint and item["status"] != "void"),
                    None,
                )
                if found is not None:
                    if found["status"] == "settled":
                        connection.rollback()
                        return {
                            "kind": "reuse",
                            "execution_id": found["id"],
                            "result": found["result"],
                            "reserved_microusd": int(found["reserved_microusd"]),
                            "snapshot": found["snapshot"],
                            "fingerprint": fingerprint,
                        }
                    raise ExposureStop("attempt_uncertain")
                if any(item["status"] == "uncertain" and not item["reconciled"] for item in rows):
                    raise ExposureStop("project_unreconciled")
                live = [item for item in rows if item["status"] != "void"]
                if len(live) >= MAX_ENGAGEMENT_ATTEMPTS:
                    raise ExposureStop("attempts_exhausted")
                spent = sum(int(item["reserved_microusd"]) for item in live)
                if spent + reserved > APPLICATION_CEILING_MICROUSD:
                    raise ExposureStop("over_cap")
                execution_id = secrets.token_hex(16)
                capability = secrets.token_hex(16)
                connection.execute(
                    """INSERT INTO execution (
                           id, project_id, report_id, capability, fingerprint, status, reconciled,
                           reserved_microusd, snapshot, used, sends, result
                       ) VALUES (%s, %s, %s, %s, %s, 'reserved', false, %s, %s, %s, 0, NULL)""",
                    (
                        execution_id,
                        project_id,
                        secrets.token_hex(16),
                        capability,
                        fingerprint,
                        reserved,
                        Jsonb(snapshot),
                        [],
                    ),
                )
                connection.commit()
                return {
                    "kind": "reserved",
                    "execution_id": execution_id,
                    "capability": capability,
                    "reserved_microusd": reserved,
                    "snapshot": snapshot,
                    "fingerprint": fingerprint,
                }
            except ExposureStop:
                connection.rollback()
                raise
            except Exception:
                connection.rollback()
                raise

    def authorize_send(self, project_id, seal, execution_id, capability, actual):
        view = _actual(actual)
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                if self._blocked(connection, project_id):
                    raise SpendClosed("paid_path_blocked")
                found = self._one(connection, project_id, execution_id)
                if found["status"] != "reserved" or found["capability"] != capability:
                    raise SpendClosed("paid_path_blocked")
                record = {"snapshot": found["snapshot"], "used": found["used"]}
                index = _match_line(record, view)
                if index is None:
                    raise SpendClosed("paid_path_blocked")
                used = found["used"] + [index]
                connection.execute(
                    """UPDATE execution SET used = %s, sends = sends + 1
                       WHERE id = %s AND project_id = %s AND status = 'reserved' AND capability = %s""",
                    (used, execution_id, project_id, capability),
                )
                connection.commit()
                return json.loads(json.dumps(found["snapshot"][index]))
            except (ExposureStop, SpendClosed):
                connection.rollback()
                raise
            except Exception:
                connection.rollback()
                raise

    def _one(self, connection, project_id, execution_id):
        row = connection.execute(
            """SELECT id, project_id, capability, status, snapshot, used, sends, reserved_microusd, result
               FROM execution WHERE id = %s AND project_id = %s FOR UPDATE""",
            (execution_id, project_id),
        ).fetchone()
        if row is None:
            raise ExposureStop("execution_rejected")
        if isinstance(row["snapshot"], str):
            row["snapshot"] = json.loads(row["snapshot"])
        row["used"] = list(row["used"] or [])
        return row

    def _blocked(self, connection, project_id):
        row = connection.execute(
            """SELECT 1 FROM execution
               WHERE project_id = %s AND status = 'uncertain' AND reconciled = false""",
            (project_id,),
        ).fetchone()
        return row is not None

    def mark_uncertain(self, project_id, seal, execution_id):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                found = self._one(connection, project_id, execution_id)
                if found["status"] == "uncertain":
                    connection.rollback()
                    return
                if found["status"] != "reserved":
                    raise ExposureStop("attempt_uncertain")
                connection.execute(
                    """UPDATE execution
                       SET status = 'uncertain', capability = %s, result = NULL
                       WHERE id = %s AND project_id = %s AND status = 'reserved'""",
                    (secrets.token_hex(16), execution_id, project_id),
                )
                connection.commit()
            except ExposureStop:
                connection.rollback()
                raise

    def stop_after_failure(self, project_id, seal, execution_id):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                found = self._one(connection, project_id, execution_id)
                if found["status"] == "void":
                    connection.rollback()
                    return
                if int(found["sends"]) == 0 and found["status"] == "reserved":
                    connection.execute(
                        """UPDATE execution SET status = 'void', capability = %s
                           WHERE id = %s AND project_id = %s AND status = 'reserved' AND sends = 0""",
                        (secrets.token_hex(16), execution_id, project_id),
                    )
                    connection.commit()
                    return
                if found["status"] == "reserved":
                    connection.execute(
                        """UPDATE execution SET status = 'uncertain', capability = %s, result = NULL
                           WHERE id = %s AND project_id = %s AND status = 'reserved'""",
                        (secrets.token_hex(16), execution_id, project_id),
                    )
                    connection.commit()
            except ExposureStop:
                connection.rollback()
                raise

    def void_unsent(self, project_id, seal, execution_id):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                found = self._one(connection, project_id, execution_id)
                if found["status"] == "void":
                    connection.rollback()
                    return
                if found["status"] != "reserved" or int(found["sends"]) != 0:
                    raise ExposureStop("attempt_uncertain")
                connection.execute(
                    """UPDATE execution
                       SET status = 'void', capability = %s
                       WHERE id = %s AND project_id = %s AND status = 'reserved' AND sends = 0""",
                    (secrets.token_hex(16), execution_id, project_id),
                )
                connection.commit()
            except ExposureStop:
                connection.rollback()
                raise

    def settle(self, project_id, seal, execution_id, result):
        if not isinstance(result, str):
            raise ExposureStop("result_unstored")
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                found = self._one(connection, project_id, execution_id)
                if found["status"] != "reserved":
                    raise ExposureStop("attempt_uncertain")
                if self._blocked(connection, project_id):
                    connection.execute(
                        """UPDATE execution
                           SET status = 'uncertain', capability = %s, result = NULL
                           WHERE id = %s AND project_id = %s AND status = 'reserved'""",
                        (secrets.token_hex(16), execution_id, project_id),
                    )
                    connection.commit()
                    return "uncertain"
                connection.execute(
                    """UPDATE execution
                       SET status = 'settled', capability = %s, result = %s
                       WHERE id = %s AND project_id = %s AND status = 'reserved'""",
                    (secrets.token_hex(16), result, execution_id, project_id),
                )
                connection.commit()
                return "settled"
            except ExposureStop:
                connection.rollback()
                raise

    def reconcile(self, project_id, seal, execution_id):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                found = self._one(connection, project_id, execution_id)
                if found["status"] != "uncertain":
                    raise ExposureStop("attempt_uncertain")
                current = connection.execute(
                    "SELECT reconciled FROM execution WHERE id = %s AND project_id = %s",
                    (execution_id, project_id),
                ).fetchone()
                if current["reconciled"]:
                    raise ExposureStop("attempt_uncertain")
                connection.execute(
                    """UPDATE execution SET reconciled = true
                       WHERE id = %s AND project_id = %s AND status = 'uncertain'""",
                    (execution_id, project_id),
                )
                connection.commit()
            except ExposureStop:
                connection.rollback()
                raise

    def accounted(self, project_id, seal):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                row = connection.execute(
                    """SELECT COUNT(*) AS n, COALESCE(SUM(reserved_microusd), 0) AS micro
                       FROM execution WHERE project_id = %s AND status <> 'void'""",
                    (project_id,),
                ).fetchone()
                connection.rollback()
                return {
                    "engagement_attempts": int(row["n"]),
                    "reserved_microusd": int(row["micro"]),
                    "engagement_attempt_cap_enforced": True,
                    "postgres_integration": "disposable_test_only",
                    "verified_price": False,
                    "production_cap": False,
                }
            except ExposureStop:
                connection.rollback()
                raise

    def report(self, project_id, seal):
        with self._connect() as connection:
            try:
                self._lock_project(connection, project_id, seal)
                rows = [
                    item for item in self._rows(connection, project_id) if item["status"] != "void"
                ]
                connection.rollback()
            except ExposureStop:
                connection.rollback()
                raise
        reserved = sum(int(item["reserved_microusd"]) for item in rows)
        executions = []
        for item in rows:
            executions.append({
                "report_id": item["report_id"],
                "status": item["status"],
                "reserved_microusd": int(item["reserved_microusd"]),
                "price_provenance": "synthetic",
                "verified_price": False,
                "services": [
                    {
                        "service": line["service"],
                        "model": line["model"],
                        "upstream_tries": line["upstream_tries"],
                        "repair_tries": line["repair_tries"],
                        "reserved_microusd": line["reserved_microusd"],
                    }
                    for line in item["snapshot"]
                ],
                "provider_reported_usage": None,
                "estimated_microusd": None,
                "billed_microusd": None,
            })
        return {
            "label": "application_exposure",
            "runtime_enforcement": False,
            "production_cap": False,
            "postgres_integration": "disposable_test_only",
            "price_provenance": "synthetic",
            "verified_price": False,
            "provider_invoice_cap": False,
            "application_ceiling_microusd": APPLICATION_CEILING_MICROUSD,
            "remaining_application_microusd": APPLICATION_CEILING_MICROUSD - reserved,
            "engagement_attempts": len(executions),
            "engagement_attempt_cap": MAX_ENGAGEMENT_ATTEMPTS,
            "engagement_attempt_cap_enforced": True,
            "amounts": {
                "reserved_worst_case_microusd": reserved,
                "estimated_microusd": None,
                "provider_reported_usage": None,
                "calculated_microusd": None,
                "billed_microusd": None,
            },
            "gaps": [
                "synthetic_price_not_a_verified_bound",
                "provider_invoice_unknown",
                "restore_not_detected",
                "http_not_armed",
            ],
            "executions": executions,
        }

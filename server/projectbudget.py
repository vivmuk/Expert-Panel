"""Offline project accounting. Not runtime enforcement and not a provider bill.

There is no dollar ceiling. A reservation is stored as given. This module does
not count engagement executions and does not stop a later reservation because
of an amount. An uncertain step stops every new reservation in that file until
`reconcile_uncertainty`. Reconciliation does not release the reservation.
Reuse requires the same service, stage, and input fingerprint. That fingerprint
stays in the file. It is not a secret and it is not written into the report.
The report id is a random value stored with the row. Facts are inserted once.
A missing observation stays null. A file whose tables are not this version is
refused before any new table is created, so an older ledger keeps its rows.

A copied file or a restored earlier copy of a valid file is not detected.
There is no monotonic anchor outside the file and no principal registry.
HTTP routes do not call this module to send.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import threading

SCHEMA_VERSION = 3
_PROJECT_COLUMNS = ("project_id", "seal_hash")
_STEP_COLUMNS = (
    "project_id",
    "identity_hash",
    "service",
    "stage",
    "status",
    "reconciled",
    "reserved_microusd",
    "result_json",
    "report_id",
)
_OBSERVATION_COLUMNS = ("project_id", "identity_hash", "kind", "body_json")
_TABLES = ("observation", "project", "step")
SERVICES = frozenset({"venice", "exa", "memory"})
STAGES = frozenset({"initial", "recovery"})
PROVIDER_CHANNEL = {"venice": "venice_inference", "exa": "venice_hosted_exa", "memory": "supermemory"}
_MISSING = object()

_locks_guard = threading.Lock()
_locks = {}


class BudgetStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def activation_blockers():
    """Why HTTP must not send, and why this file is not that enforcement."""
    return (
        "no_authenticated_project",
        "no_authoritative_attempt_price",
        "store_not_shared_across_hosts",
        "no_engagement_attempt_identity",
        "no_external_monotonic_anchor",
        "no_shared_principal_registry",
    )


def _lock(path):
    with _locks_guard:
        found = _locks.get(path)
        if found is None:
            found = threading.Lock()
            _locks[path] = found
        return found


def _reject_path(path):
    text = str(path or "").strip()
    lowered = text.lower()
    if (
        not text
        or not os.path.isabs(text)
        or lowered == ":memory:"
        or lowered.startswith("file:")
        or "mode=memory" in lowered
    ):
        raise BudgetStop("store_unproven")
    return text


def _connect(path):
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _create_schema(conn):
    """Create the current tables. Callers may use this only on a new empty file."""
    conn.execute(
        """CREATE TABLE project (
            project_id TEXT PRIMARY KEY,
            seal_hash TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE step (
            project_id TEXT NOT NULL,
            identity_hash TEXT NOT NULL,
            service TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            reconciled INTEGER NOT NULL,
            reserved_microusd INTEGER NOT NULL,
            result_json TEXT,
            report_id TEXT NOT NULL,
            PRIMARY KEY (project_id, identity_hash)
        )"""
    )
    conn.execute(
        """CREATE TABLE observation (
            project_id TEXT NOT NULL,
            identity_hash TEXT NOT NULL,
            kind TEXT NOT NULL,
            body_json TEXT NOT NULL,
            PRIMARY KEY (project_id, identity_hash, kind)
        )"""
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _column_names(conn, table):
    return tuple(row["name"] for row in conn.execute(f"PRAGMA table_info({table})"))


def _require_current_schema(conn):
    """Refuse any other layout before a statement that could create or change it."""
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    names = tuple(
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )
    if version != SCHEMA_VERSION or names != _TABLES:
        raise BudgetStop("schema_unsupported")
    if _column_names(conn, "project") != _PROJECT_COLUMNS:
        raise BudgetStop("schema_unsupported")
    if _column_names(conn, "step") != _STEP_COLUMNS:
        raise BudgetStop("schema_unsupported")
    if _column_names(conn, "observation") != _OBSERVATION_COLUMNS:
        raise BudgetStop("schema_unsupported")


def _seal_hash(seal):
    if not isinstance(seal, str) or not seal:
        raise BudgetStop("seal_rejected")
    return hashlib.sha256(seal.encode()).hexdigest()


def _identity(service, stage, inputs):
    if not isinstance(inputs, str) or not inputs:
        raise BudgetStop("step_rejected")
    raw = json.dumps(
        {"inputs": inputs, "service": service, "stage": stage},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def create_project(path):
    """Mint one project file. An existing path is refused, including a truncate."""
    path = _reject_path(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    except FileExistsError as exc:
        raise BudgetStop("store_unproven") from exc
    os.close(fd)
    project_id = secrets.token_hex(16)
    seal = secrets.token_urlsafe(32)
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            _create_schema(conn)
            conn.execute(
                "INSERT INTO project (project_id, seal_hash) VALUES (?, ?)",
                (project_id, _seal_hash(seal)),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
    return {"project_id": project_id, "seal": seal}


def _project(conn, project_id, seal):
    row = conn.execute(
        "SELECT project_id, seal_hash FROM project WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row is None or row["seal_hash"] != _seal_hash(seal):
        raise BudgetStop("seal_rejected")
    return row


def _spent(conn, project_id):
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(reserved_microusd), 0) AS micro FROM step WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return int(row["n"]), int(row["micro"])


def _open_unreconciled(conn, project_id):
    return conn.execute(
        "SELECT 1 FROM step WHERE project_id = ? AND status = 'uncertain' AND reconciled = 0",
        (project_id,),
    ).fetchone()


def decide(path, project_id, seal, inputs, service, worst_case_microusd, stage="initial"):
    """Reserve, reuse, or stop. Does not create a project and does not send.

    `worst_case_microusd` is stored as given. This function does not multiply
    it by provider retries.
    """
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    if service not in SERVICES:
        raise BudgetStop("service_unknown")
    if stage not in STAGES:
        raise BudgetStop("stage_rejected")
    if isinstance(worst_case_microusd, bool) or not isinstance(worst_case_microusd, int) or worst_case_microusd <= 0:
        raise BudgetStop("price_unknown")
    identity = _identity(service, stage, inputs)
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                _require_current_schema(conn)
                _project(conn, project_id, seal)
            except BudgetStop:
                conn.execute("ROLLBACK")
                raise
            existing = conn.execute(
                """SELECT status, service, stage, reserved_microusd, result_json
                   FROM step WHERE project_id = ? AND identity_hash = ?""",
                (project_id, identity),
            ).fetchone()
            if existing is not None:
                conn.execute("ROLLBACK")
                if existing["service"] != service or existing["stage"] != stage:
                    raise BudgetStop("step_conflict")
                if existing["status"] == "settled":
                    return {
                        "kind": "reuse",
                        "result_json": existing["result_json"],
                        "reserved_microusd": int(existing["reserved_microusd"]),
                    }
                raise BudgetStop("attempt_uncertain")
            if _open_unreconciled(conn, project_id) is not None:
                conn.execute("ROLLBACK")
                raise BudgetStop("project_unreconciled")
            conn.execute(
                """INSERT INTO step (
                       project_id, identity_hash, service, stage, status, reconciled, reserved_microusd, result_json, report_id
                   ) VALUES (?, ?, ?, ?, 'reserved', 0, ?, NULL, ?)""",
                (project_id, identity, service, stage, worst_case_microusd, secrets.token_hex(16)),
            )
            conn.execute("COMMIT")
        except BudgetStop:
            raise
        except sqlite3.Error as exc:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise BudgetStop("store_unproven") from exc
        finally:
            conn.close()
    return {"kind": "reserved", "reserved_microusd": worst_case_microusd}


def _transition(path, project_id, seal, inputs, service, stage, status, result_json):
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    identity = _identity(service, stage, inputs)
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _require_current_schema(conn)
            _project(conn, project_id, seal)
            cur = conn.execute(
                """UPDATE step SET status = ?, result_json = ?
                   WHERE project_id = ? AND identity_hash = ? AND status = 'reserved'""",
                (status, result_json, project_id, identity),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                raise BudgetStop("attempt_uncertain")
            conn.execute("COMMIT")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        except sqlite3.Error as exc:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise BudgetStop("store_unproven") from exc
        finally:
            conn.close()


def settle(path, project_id, seal, inputs, service, result_json, stage="initial"):
    if not isinstance(result_json, str):
        raise BudgetStop("result_unstored")
    _transition(path, project_id, seal, inputs, service, stage, "settled", result_json)


def mark_uncertain(path, project_id, seal, inputs, service, stage="initial"):
    _transition(path, project_id, seal, inputs, service, stage, "uncertain", None)


def reconcile_uncertainty(path, project_id, seal, inputs, service, stage="initial"):
    """Allow later reservations. The uncertain row and its amount stay."""
    path = _reject_path(path)
    identity = _identity(service, stage, inputs)
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _require_current_schema(conn)
            _project(conn, project_id, seal)
            cur = conn.execute(
                """UPDATE step SET reconciled = 1
                   WHERE project_id = ? AND identity_hash = ? AND status = 'uncertain' AND reconciled = 0""",
                (project_id, identity),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                raise BudgetStop("attempt_uncertain")
            conn.execute("COMMIT")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()


def accounted(path, project_id, seal):
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _require_current_schema(conn)
            _project(conn, project_id, seal)
            count, spent = _spent(conn, project_id)
            conn.execute("ROLLBACK")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
    return {"step_rows": count, "reserved_microusd": spent, "engagement_attempts": None}


_USAGE_KEYS = frozenset({"input_tokens", "output_tokens", "request_count"})
_PRICE_KEYS = frozenset({"input_microusd_per_token", "output_microusd_per_token", "per_request_microusd"})
_REJECTED_FACT_KEYS = frozenset({
    "prompt", "content", "messages", "text", "query", "key", "api_key", "authorization", "seal", "result",
})


def _fact_map(value, allowed):
    if value is None:
        return None
    if not isinstance(value, dict) or not value:
        raise BudgetStop("fact_rejected")
    cleaned = {}
    for key, item in value.items():
        if key in _REJECTED_FACT_KEYS or key not in allowed:
            raise BudgetStop("fact_rejected")
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise BudgetStop("fact_rejected")
        cleaned[key] = item
    return cleaned


def _calculated(usage, snapshot):
    if not usage or not snapshot:
        return None
    token_ready = (
        "input_tokens" in usage
        and "output_tokens" in usage
        and "input_microusd_per_token" in snapshot
        and "output_microusd_per_token" in snapshot
    )
    request_ready = "request_count" in usage and "per_request_microusd" in snapshot
    if token_ready and request_ready:
        return None
    if token_ready:
        return (
            usage["input_tokens"] * snapshot["input_microusd_per_token"]
            + usage["output_tokens"] * snapshot["output_microusd_per_token"]
        )
    if request_ready:
        return usage["request_count"] * snapshot["per_request_microusd"]
    return None


def record_facts(path, project_id, seal, inputs, service, usage=None, pricing_snapshot=None, billed_microusd=_MISSING, stage="initial"):
    """Insert observations once. A second write of the same kind conflicts and does not erase the first."""
    usage_map = _fact_map(usage, _USAGE_KEYS)
    price_map = _fact_map(pricing_snapshot, _PRICE_KEYS)
    if billed_microusd is _MISSING:
        billed = None
    elif isinstance(billed_microusd, bool) or not isinstance(billed_microusd, int) or billed_microusd < 0:
        raise BudgetStop("bill_rejected")
    else:
        billed = billed_microusd
    path = _reject_path(path)
    identity = _identity(service, stage, inputs)
    facts = []
    if usage_map is not None:
        facts.append(("usage", json.dumps(usage_map, sort_keys=True)))
    if price_map is not None:
        facts.append(("pricing_snapshot", json.dumps(price_map, sort_keys=True)))
    if billed is not None:
        facts.append(("billed", json.dumps(billed)))
    if not facts:
        raise BudgetStop("fact_rejected")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _require_current_schema(conn)
            _project(conn, project_id, seal)
            found = conn.execute(
                "SELECT 1 FROM step WHERE project_id = ? AND identity_hash = ?",
                (project_id, identity),
            ).fetchone()
            if found is None:
                conn.execute("ROLLBACK")
                raise BudgetStop("step_rejected")
            for kind, body in facts:
                try:
                    conn.execute(
                        "INSERT INTO observation (project_id, identity_hash, kind, body_json) VALUES (?, ?, ?, ?)",
                        (project_id, identity, kind, body),
                    )
                except sqlite3.IntegrityError as exc:
                    conn.execute("ROLLBACK")
                    raise BudgetStop("fact_conflict") from exc
            conn.execute("COMMIT")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()


def _facts_for(conn, project_id, identity):
    rows = conn.execute(
        "SELECT kind, body_json FROM observation WHERE project_id = ? AND identity_hash = ?",
        (project_id, identity),
    ).fetchall()
    return {row["kind"]: json.loads(row["body_json"]) for row in rows}


def report(path, project_id, seal, label):
    """Seal-holder view. Identifiers are fingerprints. There is no HTTP route."""
    if label not in ("synthetic", "ledger"):
        raise BudgetStop("label_rejected")
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _require_current_schema(conn)
            _project(conn, project_id, seal)
            rows = list(conn.execute(
                """SELECT identity_hash, report_id, service, stage, status, reserved_microusd
                   FROM step WHERE project_id = ? ORDER BY report_id""",
                (project_id,),
            ))
            fact_rows = {
                row["identity_hash"]: _facts_for(conn, project_id, row["identity_hash"])
                for row in rows
            }
            conn.execute("ROLLBACK")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
    steps = []
    for row in rows:
        facts = fact_rows[row["identity_hash"]]
        usage = facts.get("usage")
        snapshot = facts.get("pricing_snapshot")
        billed = facts.get("billed")
        steps.append({
            "step_id": row["report_id"],
            "provider": PROVIDER_CHANNEL[row["service"]],
            "stage": row["stage"],
            "status": row["status"],
            "reserved_worst_case_microusd": int(row["reserved_microusd"]),
            "provider_reported_usage": usage,
            "pricing_snapshot": snapshot,
            "calculated_microusd": _calculated(usage, snapshot),
            "billed_microusd": None if billed is None else int(billed),
        })
    reserved = sum(item["reserved_worst_case_microusd"] for item in steps)

    def bucket(pred):
        chosen = [item for item in steps if pred(item)]
        return {
            "step_rows": len(chosen),
            "reserved_worst_case_microusd": sum(item["reserved_worst_case_microusd"] for item in chosen),
        }

    gaps = [
        "engagement_attempt_not_counted",
        "provider_retries_not_observed",
        "no_external_monotonic_anchor",
        "failed_outcome_not_recorded",
    ]
    if any(item["provider_reported_usage"] is None for item in steps) or not steps:
        gaps.append("provider_reported_usage_missing")
    if any(item["calculated_microusd"] is None for item in steps) or not steps:
        gaps.append("calculated_cost_missing")
    if any(item["billed_microusd"] is None for item in steps) or not steps:
        gaps.append("billed_cost_missing")

    def total(field):
        values = [item[field] for item in steps]
        if not values or any(item is None for item in values):
            return None
        return int(sum(values))

    return {
        "label": label,
        "runtime_enforcement": False,
        "engagement_attempts": None,
        "engagement_attempt_cap_enforced": False,
        "initial": bucket(lambda item: item["stage"] == "initial"),
        "recovery": bucket(lambda item: item["stage"] == "recovery"),
        "successful_delivery_reserved_microusd": bucket(lambda item: item["status"] == "settled")["reserved_worst_case_microusd"],
        "inflight_reserved_microusd": bucket(lambda item: item["status"] == "reserved")["reserved_worst_case_microusd"],
        "uncertain_reserved_microusd": bucket(lambda item: item["status"] == "uncertain")["reserved_worst_case_microusd"],
        "failed_microusd": None,
        "providers": {
            "venice_inference": bucket(lambda item: item["provider"] == "venice_inference"),
            "venice_hosted_exa": bucket(lambda item: item["provider"] == "venice_hosted_exa"),
            "supermemory": bucket(lambda item: item["provider"] == "supermemory"),
        },
        "amounts": {
            "reserved_worst_case_microusd": reserved,
            "provider_reported_usage": None,
            "provider_reported_usage_scope": "per_step_only",
            "calculated_microusd": total("calculated_microusd"),
            "billed_microusd": total("billed_microusd"),
        },
        "completeness": {
            "reserved_worst_case": "complete",
            "provider_reported_usage": "missing" if "provider_reported_usage_missing" in gaps else "complete",
            "calculated": "missing" if "calculated_cost_missing" in gaps else "complete",
            "billed": "missing" if "billed_cost_missing" in gaps else "complete",
            "engagement_attempts": "not_implemented",
        },
        "gaps": gaps,
        "direct_exa_invoice": None,
        "steps": steps,
    }

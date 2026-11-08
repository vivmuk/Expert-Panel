"""Application accounting for one project. Not a provider bill.

The ceiling is 5000000 microusd, which is $5 of application accounting, and
the project may reserve at most 3 new attempts. A reservation is the caller's
worst-case amount for that attempt, including retries the caller says can
bill. Replaying a settled attempt returns the stored result and does not
reserve again. An uncertain or still-reserved attempt stops and keeps its
reservation. Nothing here refunds.

HTTP routes do not call `create_project` or `decide`. They stay closed
because three facts are missing: a project principal the request cannot mint,
an authoritative per-attempt bill cap, and a store that is shared across
hosts. A calculated token price is not that cap. `activation_blockers` is the
list HTTP code must keep in force.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import threading

APPLICATION_CEILING_MICROUSD = 5_000_000
MAX_NEW_ATTEMPTS = 3
SERVICES = frozenset({"venice", "exa", "memory"})
STAGES = frozenset({"initial", "recovery"})
# Exa search in this app is Venice /augment/search. It is not a second Exa invoice.
PROVIDER_CHANNEL = {"venice": "venice_inference", "exa": "venice_hosted_exa", "memory": "supermemory"}
_MISSING = object()

_locks_guard = threading.Lock()
_locks = {}


class BudgetStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def activation_blockers():
    """Reasons a live HTTP call must not send. Order is stable."""
    return (
        "no_authenticated_project",
        "no_authoritative_attempt_price",
        "store_not_shared_across_hosts",
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


def _ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS project (
            project_id TEXT PRIMARY KEY,
            seal_hash TEXT NOT NULL,
            ceiling_microusd INTEGER NOT NULL,
            max_attempts INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS attempt (
            project_id TEXT NOT NULL,
            step_key TEXT NOT NULL,
            service TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            reserved_microusd INTEGER NOT NULL,
            result_json TEXT,
            usage_json TEXT,
            pricing_snapshot_json TEXT,
            calculated_microusd INTEGER,
            billed_microusd INTEGER,
            PRIMARY KEY (project_id, step_key)
        )"""
    )


def _seal_hash(seal):
    if not isinstance(seal, str) or not seal:
        raise BudgetStop("seal_rejected")
    return hashlib.sha256(seal.encode()).hexdigest()


def create_project(path):
    """Mint one project file. Refuses an existing path so a truncate cannot reset."""
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
            _ensure_schema(conn)
            conn.execute(
                "INSERT INTO project (project_id, seal_hash, ceiling_microusd, max_attempts) VALUES (?, ?, ?, ?)",
                (project_id, _seal_hash(seal), APPLICATION_CEILING_MICROUSD, MAX_NEW_ATTEMPTS),
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
        "SELECT project_id, seal_hash, ceiling_microusd, max_attempts FROM project WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row is None or row["seal_hash"] != _seal_hash(seal):
        raise BudgetStop("seal_rejected")
    return row


def _spent(conn, project_id):
    row = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(reserved_microusd), 0) AS micro
           FROM attempt WHERE project_id = ?""",
        (project_id,),
    ).fetchone()
    return int(row["n"]), int(row["micro"])


def decide(path, project_id, seal, step_key, service, worst_case_microusd, stage="initial"):
    """Reserve, reuse, or stop. Does not create a project and does not send."""
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    if service not in SERVICES:
        raise BudgetStop("service_unknown")
    if stage not in STAGES:
        raise BudgetStop("stage_rejected")
    if isinstance(worst_case_microusd, bool) or not isinstance(worst_case_microusd, int) or worst_case_microusd <= 0:
        raise BudgetStop("price_unknown")
    if not isinstance(step_key, str) or not step_key or len(step_key) > 80 or any(ch.isspace() for ch in step_key):
        raise BudgetStop("step_rejected")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                _ensure_schema(conn)
                project = _project(conn, project_id, seal)
            except BudgetStop:
                conn.execute("ROLLBACK")
                raise
            existing = conn.execute(
                "SELECT status, reserved_microusd, result_json FROM attempt WHERE project_id = ? AND step_key = ?",
                (project_id, step_key),
            ).fetchone()
            if existing is not None:
                conn.execute("ROLLBACK")
                if existing["status"] == "settled":
                    return {"kind": "reuse", "result_json": existing["result_json"], "reserved_microusd": int(existing["reserved_microusd"])}
                raise BudgetStop("attempt_uncertain")
            count, spent = _spent(conn, project_id)
            if count >= int(project["max_attempts"]):
                conn.execute("ROLLBACK")
                raise BudgetStop("attempts_exhausted")
            if spent + worst_case_microusd > int(project["ceiling_microusd"]):
                conn.execute("ROLLBACK")
                raise BudgetStop("over_cap")
            conn.execute(
                """INSERT INTO attempt (
                       project_id, step_key, service, stage, status, reserved_microusd, result_json,
                       usage_json, pricing_snapshot_json, calculated_microusd, billed_microusd
                   ) VALUES (?, ?, ?, ?, 'reserved', ?, NULL, NULL, NULL, NULL, NULL)""",
                (project_id, step_key, service, stage, worst_case_microusd),
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


def _transition(path, project_id, seal, step_key, status, result_json):
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _project(conn, project_id, seal)
            cur = conn.execute(
                """UPDATE attempt SET status = ?, result_json = ?
                   WHERE project_id = ? AND step_key = ? AND status = 'reserved'""",
                (status, result_json, project_id, step_key),
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


def settle(path, project_id, seal, step_key, result_json):
    if not isinstance(result_json, str):
        raise BudgetStop("result_unstored")
    _transition(path, project_id, seal, step_key, "settled", result_json)


def mark_uncertain(path, project_id, seal, step_key):
    _transition(path, project_id, seal, step_key, "uncertain", None)


def accounted(path, project_id, seal):
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
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
    return {"attempts": count, "reserved_microusd": spent}


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
    """One basis only. Two complete bases are a gap, not a sum."""
    if not usage or not snapshot:
        return None, "missing_usage_or_snapshot"
    token_ready = (
        "input_tokens" in usage
        and "output_tokens" in usage
        and "input_microusd_per_token" in snapshot
        and "output_microusd_per_token" in snapshot
    )
    request_ready = "request_count" in usage and "per_request_microusd" in snapshot
    if token_ready and request_ready:
        return None, "more_than_one_price_basis"
    if token_ready:
        return (
            usage["input_tokens"] * snapshot["input_microusd_per_token"]
            + usage["output_tokens"] * snapshot["output_microusd_per_token"]
        ), None
    if request_ready:
        return usage["request_count"] * snapshot["per_request_microusd"], None
    return None, "pricing_snapshot_does_not_cover_usage"


def record_facts(path, project_id, seal, step_key, usage=None, pricing_snapshot=None, billed_microusd=_MISSING):
    """Store optional observations. Omitted money stays null. This does not reserve or send."""
    usage_map = _fact_map(usage, _USAGE_KEYS)
    price_map = _fact_map(pricing_snapshot, _PRICE_KEYS)
    calculated, _gap = _calculated(usage_map, price_map)
    if billed_microusd is _MISSING:
        billed = None
    elif isinstance(billed_microusd, bool) or not isinstance(billed_microusd, int) or billed_microusd < 0:
        raise BudgetStop("bill_rejected")
    else:
        billed = billed_microusd
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            _project(conn, project_id, seal)
            cur = conn.execute(
                """UPDATE attempt
                   SET usage_json = ?, pricing_snapshot_json = ?, calculated_microusd = ?, billed_microusd = ?
                   WHERE project_id = ? AND step_key = ?""",
                (
                    None if usage_map is None else json.dumps(usage_map, sort_keys=True),
                    None if price_map is None else json.dumps(price_map, sort_keys=True),
                    calculated,
                    billed,
                    project_id,
                    step_key,
                ),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                raise BudgetStop("step_rejected")
            conn.execute("COMMIT")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()


def _sum_or_unknown(rows, field):
    values = [row[field] for row in rows]
    if not values or any(item is None for item in values):
        return None
    return int(sum(values))


def report(path, project_id, seal, label):
    """Seal-holder view of one project. No prompts, results, or keys.

    `label` must say `synthetic` for an example. A shared partner API key is
    not accepted here and there is no HTTP route.
    """
    if label not in ("synthetic", "ledger"):
        raise BudgetStop("label_rejected")
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    with _lock(path):
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            project = _project(conn, project_id, seal)
            rows = conn.execute(
                """SELECT step_key, service, stage, status, reserved_microusd,
                          usage_json, pricing_snapshot_json, calculated_microusd, billed_microusd
                   FROM attempt WHERE project_id = ? ORDER BY step_key""",
                (project_id,),
            ).fetchall()
            conn.execute("ROLLBACK")
        except BudgetStop:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
    attempts = []
    for row in rows:
        attempts.append({
            "step_key": row["step_key"],
            "provider": PROVIDER_CHANNEL[row["service"]],
            "stage": row["stage"],
            "status": row["status"],
            "reserved_worst_case_microusd": int(row["reserved_microusd"]),
            "provider_reported_usage": None if row["usage_json"] is None else json.loads(row["usage_json"]),
            "pricing_snapshot": None if row["pricing_snapshot_json"] is None else json.loads(row["pricing_snapshot_json"]),
            "calculated_microusd": None if row["calculated_microusd"] is None else int(row["calculated_microusd"]),
            "billed_microusd": None if row["billed_microusd"] is None else int(row["billed_microusd"]),
        })
    reserved = sum(item["reserved_worst_case_microusd"] for item in attempts)
    ceiling = int(project["ceiling_microusd"])

    def bucket(pred):
        chosen = [item for item in attempts if pred(item)]
        return {
            "attempts": len(chosen),
            "reserved_worst_case_microusd": sum(item["reserved_worst_case_microusd"] for item in chosen),
        }

    gaps = []
    if any(item["provider_reported_usage"] is None for item in attempts) or not attempts:
        gaps.append("provider_reported_usage_missing")
    if any(item["calculated_microusd"] is None for item in attempts) or not attempts:
        gaps.append("calculated_cost_missing")
    if any(item["billed_microusd"] is None for item in attempts) or not attempts:
        gaps.append("billed_cost_missing")
    gaps.append("failed_outcome_not_recorded")
    return {
        "label": label,
        "application_ceiling_microusd": ceiling,
        "remaining_application_microusd": ceiling - reserved,
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
            "provider_reported_usage_scope": "per_attempt_only",
            "calculated_microusd": _sum_or_unknown(attempts, "calculated_microusd"),
            "billed_microusd": _sum_or_unknown(attempts, "billed_microusd"),
        },
        "completeness": {
            "reserved_worst_case": "complete",
            "provider_reported_usage": "missing" if "provider_reported_usage_missing" in gaps else "complete",
            "calculated": "missing" if "calculated_cost_missing" in gaps else "complete",
            "billed": "missing" if "billed_cost_missing" in gaps else "complete",
        },
        "gaps": gaps,
        "direct_exa_invoice": None,
        "attempts": attempts,
    }

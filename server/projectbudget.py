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
import os
import secrets
import sqlite3
import threading

APPLICATION_CEILING_MICROUSD = 5_000_000
MAX_NEW_ATTEMPTS = 3
SERVICES = frozenset({"venice", "exa", "memory"})

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
            status TEXT NOT NULL,
            reserved_microusd INTEGER NOT NULL,
            result_json TEXT,
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


def decide(path, project_id, seal, step_key, service, worst_case_microusd):
    """Reserve, reuse, or stop. Does not create a project and does not send."""
    path = _reject_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise BudgetStop("store_unproven")
    if service not in SERVICES:
        raise BudgetStop("service_unknown")
    if isinstance(worst_case_microusd, bool) or not isinstance(worst_case_microusd, int) or worst_case_microusd <= 0:
        raise BudgetStop("price_unknown")
    if not isinstance(step_key, str) or not step_key:
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
                """INSERT INTO attempt (project_id, step_key, service, status, reserved_microusd, result_json)
                   VALUES (?, ?, ?, 'reserved', ?, NULL)""",
                (project_id, step_key, service, worst_case_microusd),
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

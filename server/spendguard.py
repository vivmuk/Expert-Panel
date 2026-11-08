"""Fail-closed gate in front of paid provider work.

A calculated unit price times a call count is not a provider bill. A missing
price is not free. This module does not invent a currency cap. Paid work is
sent only when an operator opts into a single-host SQLite ledger and sets a
calculated ceiling and calculated unit prices. Otherwise the call is refused
before any provider I/O.

The ledger is one SQLite file. It is not shared by Railway, Maritime, and
Vercel. Vercel has no durable file in this app, so paid work stays closed
there. A row left `dispatched` is an uncertain charge: later calls return that
row and do not send the phase again.
"""
import hashlib
import json
import os
import sqlite3
from contextvars import ContextVar

VENICE_ATTEMPTS = 3
EXA_QUERIES = 6

_phase = ContextVar("spend_phase", default=None)

CLOSED = {
    "spend_ledger_unavailable": (
        "Paid work is stopped. No durable single-host spend ledger is configured, "
        "so this step was not sent to a provider."
    ),
    "currency_bound_unavailable": (
        "Paid work is stopped. No provider bill cap is configured. "
        "A calculated price is not a bill. This step was not sent."
    ),
    "calculated_price_unavailable": (
        "Paid work is stopped. A calculated unit price is missing, zero, or negative. "
        "That is not free. This step was not sent."
    ),
    "calculated_ceiling_exceeded": (
        "Paid work is stopped. This step would pass the configured calculated ceiling. "
        "The ceiling is not a provider bill. This step was not sent."
    ),
    "phase_uncertain": (
        "Paid work is stopped. This step was already sent, or it stopped after the send "
        "was committed and before a result was stored. It was not sent again."
    ),
    "paid_path_blocked": (
        "Paid work is stopped. This provider call is outside a reserved phase. "
        "It was not sent."
    ),
}


class SpendClosed(Exception):
    def __init__(self, code):
        self.code = code
        self.message = CLOSED[code]
        super().__init__(self.message)


class provider_window:
    """Lets a caller that already reserved, or a local HTTP stub test, reach the provider client."""

    def __enter__(self):
        self._token = _phase.set("open")
        return self

    def __exit__(self, *_exc):
        _phase.reset(self._token)
        return False


def in_phase():
    return _phase.get() is not None


def require_open_phase():
    if not in_phase():
        raise SpendClosed("paid_path_blocked")


def _positive_int(name):
    raw = os.environ.get(name, "").strip()
    if not raw or not raw.isdigit():
        return None
    value = int(raw)
    return value if value > 0 else None


def _ledger_path():
    if os.environ.get("VERCEL"):
        return None
    if os.environ.get("AI_PARTNER_SPEND_LEDGER", "").strip().lower() != "sqlite":
        return None
    path = os.environ.get("AI_PARTNER_SPEND_LEDGER_PATH", "").strip()
    if not path:
        return None
    return path


def _needs_exa(state):
    return state.get("phase") == "research" and bool(os.environ.get("VENICE_API_KEY", "").strip())


def _needs_memory(state):
    return state.get("phase") in ("research", "judge") and bool(os.environ.get("SUPERMEMORY_API_KEY", "").strip())


def _attempt_price(state):
    phase = state.get("phase")
    if phase == "voice":
        return _positive_int("AI_PARTNER_CALCULATED_MICROUSD_VOICE")
    if phase == "brand":
        return _positive_int("AI_PARTNER_CALCULATED_MICROUSD_IMAGE")
    return _positive_int("AI_PARTNER_CALCULATED_MICROUSD_VENICE_ATTEMPT")


def readiness(state):
    """Return a SpendClosed code, or None when a calculated reservation is possible."""
    if _ledger_path() is None:
        return "spend_ledger_unavailable"
    if _positive_int("AI_PARTNER_CALCULATED_CEILING_MICROUSD") is None:
        return "currency_bound_unavailable"
    if _attempt_price(state) is None:
        return "calculated_price_unavailable"
    if _needs_exa(state) and _positive_int("AI_PARTNER_CALCULATED_MICROUSD_EXA") is None:
        return "calculated_price_unavailable"
    if _needs_memory(state) and _positive_int("AI_PARTNER_CALCULATED_MICROUSD_MEMORY") is None:
        return "calculated_price_unavailable"
    return None


def exposure_microusd(state):
    total = VENICE_ATTEMPTS * _attempt_price(state)
    if _needs_exa(state):
        total += EXA_QUERIES * _positive_int("AI_PARTNER_CALCULATED_MICROUSD_EXA")
    if _needs_memory(state):
        total += _positive_int("AI_PARTNER_CALCULATED_MICROUSD_MEMORY")
    return total


def phase_key(state):
    body = {
        "chat_id": str(state.get("chat_id") or ""),
        "phase": str(state.get("phase") or ""),
        "problem": str(state.get("problem") or ""),
        "team": str(state.get("team") or ""),
        "tools": str(state.get("tools") or ""),
        "maturity": state.get("maturity"),
        "experts": len(state.get("experts") or []),
        "debate_done": int(state.get("debate_done") or 0),
        "size": str(state.get("size") or ""),
        "artifact": str(state.get("_spend_artifact") or ""),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _connect(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS spend_phase (
            phase_key TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            exposure_microusd INTEGER NOT NULL,
            result_json TEXT
        )"""
    )
    return conn


def _lookup(conn, key):
    return conn.execute("SELECT status, result_json FROM spend_phase WHERE phase_key = ?", (key,)).fetchone()


def _used(conn):
    row = conn.execute("SELECT COALESCE(SUM(exposure_microusd), 0) AS n FROM spend_phase").fetchone()
    return int(row["n"])


def run_paid_phase(state, fn):
    """Run fn at most once for this phase key. Refuse before fn when the ledger cannot reserve."""
    code = readiness(state)
    if code:
        raise SpendClosed(code)
    path = _ledger_path()
    key = phase_key(state)
    exposure = exposure_microusd(state)
    ceiling = _positive_int("AI_PARTNER_CALCULATED_CEILING_MICROUSD")
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _lookup(conn, key)
        if row and row["status"] == "settled":
            conn.execute("ROLLBACK")
            return json.loads(row["result_json"])
        if row:
            conn.execute("ROLLBACK")
            raise SpendClosed("phase_uncertain")
        if _used(conn) + exposure > ceiling:
            conn.execute("ROLLBACK")
            raise SpendClosed("calculated_ceiling_exceeded")
        conn.execute(
            "INSERT INTO spend_phase (phase_key, status, exposure_microusd, result_json) VALUES (?, 'dispatched', ?, NULL)",
            (key, exposure),
        )
        conn.execute("COMMIT")
    except SpendClosed:
        raise
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()

    token = _phase.set(key)
    try:
        result = fn()
        try:
            stored = json.dumps(result, separators=(",", ":"))
        except TypeError:
            stored = json.dumps({"replay": "unavailable"})
        conn = _connect(path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE spend_phase SET status = 'settled', result_json = ? WHERE phase_key = ? AND status = 'dispatched'",
                (stored, key),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()
        return result
    finally:
        # A raised error leaves the row dispatched, which a later call treats as an uncertain charge.
        _phase.reset(token)

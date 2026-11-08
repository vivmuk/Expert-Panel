"""Paid provider execution stays closed.

No authoritative provider bill is available in this process. A configured
positive integer is not that bill, so HTTP routes do not send provider work.
Voice, images, the model catalog, and legacy runs stay closed for the same
reason.

`claim_send` is only a file note that a non-streaming call may write once.
It is not permission to run a chat, not a currency cap, and not a stored
result. `release_send` deletes that note, so the same key can be claimed
again. A new process can claim again after the file is replaced or truncated.
Those limits are activation blockers. HTTP routes do not pass a journal.
"""
import hashlib
import json
import os
import sqlite3
import stat

CLOSED = {
    "currency_bound_unavailable": (
        "Paid work is stopped. No authoritative provider bill bound is available. "
        "A configured number is not a bill. This step was not sent."
    ),
    "spend_ledger_unavailable": (
        "Paid work is stopped. This process has no durable file that can record an "
        "uncertain send. This step was not sent."
    ),
    "phase_uncertain": (
        "Paid work is stopped. This send was already attempted and its response was "
        "not stored. It was not sent again."
    ),
    "paid_path_blocked": (
        "Paid work is stopped. This provider call is outside a reserved send. "
        "It was not sent."
    ),
}

_identities = {}
_lost = set()


class SpendClosed(Exception):
    def __init__(self, code):
        self.code = code
        self.message = CLOSED[code]
        super().__init__(self.message)


def refuse_paid():
    """Production entry points call this before any provider I/O."""
    raise SpendClosed("currency_bound_unavailable")


def run_paid_phase(state, fn):
    """Do not call fn. An operator integer is not a bill bound."""
    del state, fn
    refuse_paid()


def operation_key(method, path, body):
    raw = json.dumps(
        {"method": method, "path": path, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _reject_ephemeral(path):
    text = str(path or "").strip()
    lowered = text.lower()
    if (
        not text
        or not os.path.isabs(text)
        or lowered == ":memory:"
        or lowered.startswith("file:")
        or "mode=memory" in lowered
    ):
        raise SpendClosed("spend_ledger_unavailable")
    return text


def _identity(path):
    try:
        st = os.stat(path)
    except OSError as exc:
        raise SpendClosed("spend_ledger_unavailable") from exc
    if not stat.S_ISREG(st.st_mode):
        raise SpendClosed("spend_ledger_unavailable")
    ident = (st.st_dev, st.st_ino)
    known = _identities.get(path)
    if known is not None and known != ident:
        raise SpendClosed("phase_uncertain")
    return ident


def _connect(path):
    path = _reject_ephemeral(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    ident = _identity(path)
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS send_hold (
            op_key TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE TABLE IF NOT EXISTS send_probe (n INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR REPLACE INTO send_probe (n) VALUES (1)")
    other = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        seen = other.execute("SELECT n FROM send_probe").fetchone()
    finally:
        other.close()
    if not seen:
        conn.close()
        raise SpendClosed("spend_ledger_unavailable")
    _identities[path] = ident
    return conn


def _visible(path, key, status):
    other = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        row = other.execute("SELECT status FROM send_hold WHERE op_key = ?", (key,)).fetchone()
    finally:
        other.close()
    return row is not None and row[0] == status


def claim_send(path, key):
    """Record a pending send on a real file, or refuse before the socket write."""
    if (path, key) in _lost:
        raise SpendClosed("phase_uncertain")
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM send_hold WHERE op_key = ?", (key,)).fetchone()
        if row is not None:
            conn.execute("ROLLBACK")
            _lost.add((path, key))
            raise SpendClosed("phase_uncertain")
        conn.execute("INSERT INTO send_hold (op_key, status) VALUES (?, 'pending')", (key,))
        conn.execute("COMMIT")
    except SpendClosed:
        raise
    except sqlite3.Error as exc:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise SpendClosed("spend_ledger_unavailable") from exc
    finally:
        conn.close()
    if not _visible(path, key, "pending"):
        _lost.add((path, key))
        raise SpendClosed("spend_ledger_unavailable")


def lose_send(path, key):
    """The socket write may have been accepted. Keep the row uncertain."""
    _lost.add((path, key))
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE send_hold SET status = 'uncertain' WHERE op_key = ? AND status = 'pending'",
            (key,),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            raise SpendClosed("phase_uncertain")
        conn.execute("COMMIT")
    except SpendClosed:
        raise
    except sqlite3.Error as exc:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise SpendClosed("phase_uncertain") from exc
    finally:
        conn.close()
    if not _visible(path, key, "uncertain"):
        raise SpendClosed("phase_uncertain")


def release_send(path, key):
    """A completed HTTP response arrived. Drop the pending row only."""
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM send_hold WHERE op_key = ?", (key,)).fetchone()
        if row is None or row["status"] != "pending":
            conn.execute("ROLLBACK")
            _lost.add((path, key))
            raise SpendClosed("phase_uncertain")
        cur = conn.execute("DELETE FROM send_hold WHERE op_key = ? AND status = 'pending'", (key,))
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            _lost.add((path, key))
            raise SpendClosed("phase_uncertain")
        conn.execute("COMMIT")
    except SpendClosed:
        raise
    except sqlite3.Error as exc:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        _lost.add((path, key))
        raise SpendClosed("phase_uncertain") from exc
    finally:
        conn.close()

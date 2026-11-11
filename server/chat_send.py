import os
import threading
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar

_open = ContextVar("user_chat_send", default=False)
_lock = threading.Lock()
_REPORTED_LIMIT = 256
_reported = deque(maxlen=_REPORTED_LIMIT)
RAILWAY_MARKERS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_ID",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_SERVICE_NAME",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_DEPLOYMENT_ID",
    "RAILWAY_REPLICA_ID",
)


def secret_text(value):
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or any(ch.isspace() for ch in text):
        return ""
    return text


def usable_secret(value):
    return bool(secret_text(value))


def allowed():
    return _open.get() is True


def _present(name):
    return bool(os.environ.get(name, "").strip())


def host_may_send():
    """Railway's own service variables open the chat even when VERCEL=1 is also set."""
    if any(_present(name) for name in RAILWAY_MARKERS):
        return True
    return not _present("VERCEL")


def open_worker():
    """Search workers do not inherit the request context on this interpreter."""
    _open.set(True)


@contextmanager
def user_chat_send():
    token = _open.set(host_may_send())
    try:
        yield
    finally:
        _open.reset(token)


def note(service, payload):
    usage, cost = split_report(payload)
    with _lock:
        _reported.append({"service": service, "usage": usage, "cost_usd": cost})


def reported():
    with _lock:
        return [dict(row) for row in _reported]


def reset_reported():
    with _lock:
        _reported.clear()


def split_report(payload):
    if not isinstance(payload, dict):
        return None, None
    if "usage" not in payload:
        usage = None
    elif isinstance(payload.get("usage"), dict):
        usage = dict(payload["usage"])
    else:
        usage = None
    if "cost_usd" in payload:
        cost = _number(payload.get("cost_usd"))
    elif isinstance(usage, dict) and "cost_usd" in usage:
        cost = _number(usage.get("cost_usd"))
    else:
        cost = None
    return usage, cost


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value

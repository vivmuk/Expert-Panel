import hashlib
import logging
import os
import re
import threading

import requests

from .chatjob import safe_id

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 4
WRITE_URL = "https://api.supermemory.ai/v3/documents"
_ERROR_BODY_LIMIT = 500
_written_guard = threading.Lock()
_written = set()
# customId -> sha256 of the snapshot last posted. A repeat of that text is skipped
# so a retried verdict on this worker does not append a second copy.
_snapshots = {}


def namespace(chat_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", chat_id or "")[:48]
    return "chat-" + (safe or "anon")


def memory_namespace(chat_id, visitor_id=None):
    """One namespace per browser when the client sent a visitor id, else one per chat."""
    visitor = safe_id(visitor_id)
    if visitor:
        return "visitor-" + visitor
    return namespace(chat_id)


def reset_written():
    with _written_guard:
        _written.clear()
        _snapshots.clear()


def _was_written(ns):
    with _written_guard:
        return ns in _written


def _note_written(ns):
    with _written_guard:
        _written.add(ns)


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _same_snapshot(doc_id, text):
    with _written_guard:
        return _snapshots.get(doc_id) == _digest(text)


def _note_snapshot(doc_id, text):
    with _written_guard:
        _snapshots[doc_id] = _digest(text)


def _custom_id(ns, chat_id):
    chat = safe_id(chat_id) or "anon"
    return ns + "-" + chat


def _scalar_metadata(fields):
    """Supermemory metadata values are scalars. Drop anything nested."""
    kept = {}
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)):
            kept[key] = value
    return kept


def _response_body(response, key):
    if response is None:
        return ""
    try:
        text = response.text
    except Exception:
        return ""
    if not isinstance(text, str):
        return ""
    if key:
        text = text.replace(key, "[redacted]")
    return text[:_ERROR_BODY_LIMIT]


def _may_search(ns, has_history):
    # Empty searches are what the Supermemory dashboard flags. Search only after a
    # write in this process, or when a returning visitor says this browser has one.
    if _was_written(ns):
        return True
    return has_history is True and ns.startswith("visitor-")


def _key():
    return os.environ.get("SUPERMEMORY_API_KEY", "").strip()


def _headers(key):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def recall(chat_id, query, visitor_id=None, has_history=False):
    key = _key()
    if not key or not query:
        return ""
    from .exposure import current

    active = current()
    if active is None:
        from .spendguard import refuse_paid

        refuse_paid()
    from .exposure import describe_recall

    transport, bound = active.consume(describe_recall(chat_id, query, visitor_id, has_history))
    return transport.recall(bound)


def remember(chat_id, content, visitor_id=None):
    """Memory writes stay closed unless an offline execution reserved this call."""
    key = _key()
    if not key or not content:
        return
    from .exposure import current

    active = current()
    if active is None:
        from .spendguard import refuse_paid

        refuse_paid()
    from .exposure import describe_remember

    transport, bound = active.consume(describe_remember(chat_id, content, visitor_id))
    return transport.remember(bound)

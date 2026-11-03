import logging
import os
import re
import threading

import requests

from .chatjob import safe_id

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 4
_written_guard = threading.Lock()
_written = set()


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


def _was_written(ns):
    with _written_guard:
        return ns in _written


def _note_written(ns):
    with _written_guard:
        _written.add(ns)


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
    ns = memory_namespace(chat_id, visitor_id)
    if not _may_search(ns, has_history):
        return ""
    try:
        response = requests.post(
            f"https://api.supermemory.ai/ns/{ns}/search",
            headers=_headers(key),
            json={"query": query[:500], "searchMode": "hybrid", "limit": 3},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.info("supermemory recall failed for %s", ns)
        return ""
    parts = []
    for item in (payload.get("results") or [])[:3]:
        if not isinstance(item, dict):
            continue
        text = item.get("memory") or item.get("chunk") or ""
        if isinstance(text, str) and text.strip():
            parts.append(" ".join(text.split()))
    return "\n".join(parts)[:800]


def remember(chat_id, content, visitor_id=None):
    key = _key()
    if not key or not content:
        return
    ns = memory_namespace(chat_id, visitor_id)
    chat = safe_id(chat_id) or "anon"
    if ns.startswith("visitor-"):
        doc_id = ns + "-" + chat
        body = {
            "content": content[:8000],
            "id": doc_id,
            "customId": doc_id,
            "containerTag": ns,
            "metadata": {"type": "engagement"},
        }
    else:
        body = {
            "content": content[:8000],
            "id": ns,
            "metadata": {"type": "engagement"},
        }
    try:
        response = requests.post(
            f"https://api.supermemory.ai/ns/{ns}/document",
            headers=_headers(key),
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception:
        logger.info("supermemory remember failed for %s", ns)
        return
    _note_written(ns)

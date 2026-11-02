"""Optional Supermemory recall for one chat.

No-op when SUPERMEMORY_API_KEY is unset. Failures stay in the log so a memory
outage does not stop the job.
"""
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 4


def namespace(chat_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", chat_id or "")[:48]
    return "chat-" + (safe or "anon")


def _key():
    return os.environ.get("SUPERMEMORY_API_KEY", "").strip()


def recall(chat_id, query):
    key = _key()
    if not key or not query:
        return ""
    try:
        response = requests.post(
            f"https://api.supermemory.ai/ns/{namespace(chat_id)}/search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query[:500], "searchMode": "hybrid", "limit": 3},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.info("supermemory recall failed for %s", namespace(chat_id))
        return ""
    parts = []
    for item in (payload.get("results") or [])[:3]:
        if not isinstance(item, dict):
            continue
        text = item.get("memory") or item.get("chunk") or ""
        if isinstance(text, str) and text.strip():
            parts.append(" ".join(text.split()))
    return "\n".join(parts)[:800]


def remember(chat_id, content):
    key = _key()
    if not key or not content:
        return
    try:
        response = requests.post(
            f"https://api.supermemory.ai/ns/{namespace(chat_id)}/document",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "content": content[:8000],
                "id": namespace(chat_id),
                "metadata": {"type": "engagement"},
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception:
        logger.info("supermemory remember failed for %s", namespace(chat_id))

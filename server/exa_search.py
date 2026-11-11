import os

import requests

EXA_URL = "https://api.venice.ai/api/v1/augment/search"
EXA_TIMEOUT = int(os.environ.get("EXA_TIMEOUT_SECONDS", "25"))


def exa_search(query, limit=4, api_key=None):
    from .chat_send import secret_text

    raw = api_key if api_key is not None else os.environ.get("VENICE_API_KEY", "")
    key = secret_text(raw)
    if not key or not query:
        return []
    from .exposure import current

    active = current()
    if active is not None:
        from .exposure import describe_exa

        transport, bound = active.consume(describe_exa(query, limit))
        return transport.search(bound)
    from .chat_send import allowed

    if not allowed():
        from .spendguard import refuse_paid

        refuse_paid()
    capped = max(1, min(int(limit), 20))
    response = requests.post(
        os.environ.get("EXA_URL", EXA_URL),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "limit": capped, "search_provider": "exa"},
        timeout=EXA_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    from .chat_send import note

    note("exa", payload)
    found = []
    for item in (payload.get("results") or [])[:capped]:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or ""
        if not url:
            continue
        found.append(
            {
                "title": str(item.get("title") or url)[:180],
                "url": str(url)[:400],
                "content": str(item.get("content") or "")[:500],
                "date": str(item.get("date") or "")[:40],
            }
        )
    return found

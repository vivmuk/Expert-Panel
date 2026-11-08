import os

import requests

EXA_URL = "https://api.venice.ai/api/v1/augment/search"
EXA_TIMEOUT = int(os.environ.get("EXA_TIMEOUT_SECONDS", "25"))


def exa_search(query, limit=4, api_key=None):
    key = api_key if api_key is not None else os.environ.get("VENICE_API_KEY", "")
    if not key or not query:
        return []
    from .exposure import current

    active = current()
    if active is None:
        from .spendguard import refuse_paid

        refuse_paid()
    del limit
    return active.consume("exa").search()

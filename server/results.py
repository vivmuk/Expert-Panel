"""Unlisted copies of a finished engagement. The token is the only secret."""
import json
import os
import re
import secrets

from .config import Config

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def new_token():
    return secrets.token_urlsafe(32)


def save_result(state):
    token = new_token()
    folder = os.path.join(Config.DATA_DIR, "results")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, token + ".json")
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(temp, path)
    return token


def load_result(token):
    if not isinstance(token, str) or not _TOKEN.match(token):
        return None
    path = os.path.join(Config.DATA_DIR, "results", token + ".json")
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None

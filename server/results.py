"""Unlisted copies of a finished engagement. The token is the only secret."""
import json
import os
import re
import secrets

from .config import Config

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def new_token():
    return secrets.token_urlsafe(32)


def _write_file(token, state):
    folder = os.path.join(Config.DATA_DIR, "results")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, token + ".json")
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(temp, path)


def _read_file(token):
    path = os.path.join(Config.DATA_DIR, "results", token + ".json")
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def save_result(state):
    token = new_token()
    from .hostrole import database_allowed

    if database_allowed():
        try:
            from .accounts import save_json

            save_json("result", token, state)
        except Exception:
            _write_file(token, state)
    else:
        _write_file(token, state)
    return token


def load_result(token):
    if not isinstance(token, str) or not _TOKEN.match(token):
        return None
    from .hostrole import database_allowed

    if database_allowed():
        try:
            from .accounts import load_json

            state = load_json("result", token)
            if isinstance(state, dict):
                return state
        except Exception:
            pass
    return _read_file(token)

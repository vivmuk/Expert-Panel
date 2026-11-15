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


def _persist(token, state):
    from .hostrole import database_allowed

    if database_allowed():
        try:
            from .accounts import save_json

            save_json("result", token, state)
            return
        except Exception:
            pass
    _write_file(token, state)


def save_result(state):
    token = new_token()
    _persist(token, state)
    return token


_JOB_ID = re.compile(r"^job_[0-9a-f]{24}$")


def _chat_key(state):
    from .chatjob import safe_id

    chat_id = state.get("chat_id") if isinstance(state, dict) else None
    safe = safe_id(chat_id) if isinstance(chat_id, str) else ""
    return "chat:" + safe if safe else ""


def _job_keys(state, job_id):
    keys = []
    chat_key = _chat_key(state)
    if chat_key:
        keys.append(chat_key)
    if isinstance(job_id, str) and _JOB_ID.match(job_id):
        keys.append("job:" + job_id)
    return keys


def _token_of(body):
    if not isinstance(body, dict):
        return None
    token = body.get("token")
    if isinstance(token, str) and _TOKEN.match(token):
        return token
    return None


def _map_path(key):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", key)[:120]
    return os.path.join(Config.DATA_DIR, "results", "maps", safe + ".json")


def _read_map_file(key):
    try:
        with open(_map_path(key), encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _read_map(key):
    from .hostrole import database_allowed

    if database_allowed():
        try:
            from .accounts import load_json

            token = _token_of(load_json("result", "map:" + key))
            if token:
                return token
        except Exception:
            pass
    return _token_of(_read_map_file(key))


def _claim_map_file(key, token):
    path = _map_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{token}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump({"token": token}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temp, path)
    except FileExistsError:
        os.remove(temp)
        return _token_of(_read_map_file(key)) or token
    os.remove(temp)
    return token


def _claim_map(key, token):
    from .hostrole import database_allowed

    if database_allowed():
        try:
            from .accounts import claim_json

            found = _token_of(claim_json("result", "map:" + key, {"token": token}))
            if found:
                return found
        except Exception:
            pass
    return _claim_map_file(key, token)


def _find_token(keys):
    for key in keys:
        token = _read_map(key)
        if token:
            return token
    return None


def save_shared_result(state, job_id=None):
    if not isinstance(state, dict) or state.get("phase") != "done":
        raise ValueError("not done")
    keys = _job_keys(state, job_id)
    if not keys:
        raise ValueError("missing job")
    existing = _find_token(keys)
    if existing:
        for key in keys:
            _claim_map(key, existing)
        return _find_token(keys) or existing
    minted = new_token()
    winner = _claim_map(keys[0], minted)
    if winner == minted:
        _persist(minted, state)
    for key in keys[1:]:
        _claim_map(key, winner)
    return _find_token(keys) or winner


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

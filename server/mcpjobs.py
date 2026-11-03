"""Job state kept server-side for MCP clients that cannot carry it between calls, such as messaging agents.

A job is stored under a hash of the caller's bearer key and the job id, so one key never reads another key's job.
"""
import hashlib
import json
import os
import re
import secrets
import time

from .config import Config

TTL_SECONDS = 7 * 24 * 60 * 60
_ID = re.compile(r"^job_[0-9a-f]{24}$")


def new_id():
    return "job_" + secrets.token_hex(12)


def _path(owner, job_id):
    digest = hashlib.sha256(f"{owner}|{job_id}".encode()).hexdigest()
    return os.path.join(Config.DATA_DIR, "jobs", digest + ".json")


def save(owner, job_id, state):
    path = _path(owner, job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _sweep(os.path.dirname(path))
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(temp, path)


def load(owner, job_id):
    if not isinstance(job_id, str) or not _ID.match(job_id):
        return None
    path = _path(owner, job_id)
    try:
        if time.time() - os.path.getmtime(path) > TTL_SECONDS:
            os.remove(path)
            return None
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def _sweep(folder):
    cutoff = time.time() - TTL_SECONDS
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            continue

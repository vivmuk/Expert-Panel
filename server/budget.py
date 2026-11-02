"""Call budget that does not trust a client-supplied counter."""
import hashlib
import hmac
import threading
import time

from .keys import signing_secrets

WINDOW_SECONDS = 86400
MAX_JOBS = 2000
_lock = threading.Lock()
_spent = {}


class TamperedState(Exception):
    pass


class BudgetUnavailable(Exception):
    """No signing secret is set, so a client-sent call count cannot be checked."""


def reset():
    with _lock:
        _spent.clear()


def reconcile_calls(chat_id, claimed, sig, now=None):
    """Return the call count to enforce.

    A signed count must match its HMAC and an unsigned count is ignored.
    Without a signing secret nothing can be checked, so refuse. The stored
    count never goes down.
    """
    now = time.time() if now is None else now
    if isinstance(claimed, bool) or not isinstance(claimed, int) or claimed < 0:
        claimed = 0
    secrets = signing_secrets()
    if not secrets:
        raise BudgetUnavailable()
    if not sig:
        base = 0
    elif not sig_matches(chat_id, claimed, sig, secrets):
        raise TamperedState()
    else:
        base = claimed
    with _lock:
        _evict(now)
        prev, _seen = _spent.get(chat_id, (0, now))
        actual = max(prev, base)
        _spent[chat_id] = (actual, now)
        return actual


def commit_calls(chat_id, calls, now=None):
    now = time.time() if now is None else now
    with _lock:
        prev, _seen = _spent.get(chat_id, (0, now))
        _spent[chat_id] = (max(prev, int(calls)), now)


def sign_calls(chat_id, calls):
    secrets = signing_secrets()
    if not secrets:
        return ""
    kid = "v1" if "v1" in secrets else next(iter(secrets))
    secret = secrets[kid]
    mac = hmac.new(secret.encode(), _msg(kid, chat_id, calls), hashlib.sha256).hexdigest()
    return f"{kid}.{mac}"


def sig_matches(chat_id, calls, sig, secrets):
    if not isinstance(sig, str) or sig.count(".") != 1:
        return False
    kid, mac = sig.split(".", 1)
    secret = secrets.get(kid)
    if not secret:
        return False
    expect = hmac.new(secret.encode(), _msg(kid, chat_id, calls), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, mac)


def _msg(kid, chat_id, calls):
    return f"{kid}|{chat_id}|{int(calls)}".encode()


def _evict(now):
    stale = [key for key, (_calls, seen) in _spent.items() if now - seen >= WINDOW_SECONDS]
    for key in stale:
        _spent.pop(key, None)
    if len(_spent) <= MAX_JOBS:
        return
    oldest = sorted(_spent.items(), key=lambda item: item[1][1])
    for key, _value in oldest[: len(_spent) - MAX_JOBS]:
        _spent.pop(key, None)

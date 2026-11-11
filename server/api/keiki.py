"""Keiki external harness (push mode).

Keiki POSTs a signed `keiki.turn` to /keiki/turn. We verify `Keiki-Signature`
(HMAC-SHA256 over "<t>.<raw body>") with KEIKI_HARNESS_SIGNING_SECRET, answer 202,
run the existing chat engine in a background thread, then reply through
POST {turnUrl}/messages and settle with POST {turnUrl}/complete.
Docs: https://onkeiki.com/docs/external-harness.md
"""

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time

import requests
from flask import Blueprint, jsonify, request

bp = Blueprint("keiki", __name__)
logger = logging.getLogger(__name__)

MAX_SKEW = 300
MAX_TEXT = 3500
MAX_STEPS = 30  # one engagement is ~13 engine steps; Keiki's turn deadline is 10 minutes
TURN_DEADLINE = 480  # stop before Keiki's 10 minute turn deadline, so a stuck run cannot keep spending
MAX_CONVERSATIONS = 500
MAX_SEEN = 2000
ACK = (
    "Hi, this is AI Partner — thanks for texting. I’ve got your note and I’m starting your engagement now. "
    "A full run usually takes about 4 minutes. I’ll text you a link when the report is ready."
)
SORRY = (
    "I hit a snag and couldn’t finish this run. Sorry about that — text me the problem again and I’ll start a fresh one."
)
QUESTIONS = {"ask_problem", "ask_followup", "ask_context", "ask_maturity", "ask_size"}
_states = {}  # (agentId, contact) -> engine state; also written under DATA_DIR so the next turn can load it
_seen = {}  # signature digest -> time; replays inside the skew window are rejected
_lock = threading.Lock()
_seen_lock = threading.Lock()


def _secret():
    return os.environ.get("KEIKI_HARNESS_SIGNING_SECRET", "")


def reset_replays():
    with _seen_lock:
        _seen.clear()


def _fresh(raw, header, now):
    """True the first time this exact signed body is seen inside the skew window."""
    digest = hashlib.sha256(header.encode() + b"\n" + raw).hexdigest()
    with _seen_lock:
        stale = [key for key, seen in _seen.items() if now - seen > MAX_SKEW]
        for key in stale:
            _seen.pop(key, None)
        if digest in _seen:
            return False
        _seen[digest] = now
        if len(_seen) > MAX_SEEN:
            _seen.pop(min(_seen, key=_seen.get), None)
        return True


def verify(raw, header, secret, now=None):
    if not secret or not header:
        return False
    parts = dict(p.strip().split("=", 1) for p in header.split(",") if "=" in p)
    try:
        ts = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > MAX_SKEW:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))


def _engine(message, state):
    from .agents import _turn

    return _turn(message, state)


def _post(url, token, body):
    response = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    response.raise_for_status()
    return response


def _chat_dir():
    from ..config import Config

    return os.path.join(Config.DATA_DIR, "keiki-chats")


def reset_conversations():
    with _lock:
        _states.clear()
    folder = _chat_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            continue


def _canon(value):
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if "@" in text:
        return text.lower()
    digits = re.sub(r"\D", "", text)
    marks = sum(text.count(ch) for ch in "+ ()-.")
    if len(digits) >= 10 and len(digits) >= len(text) - marks:
        return "+" + digits
    return text


def _candidates(payload):
    found = []
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    for source in (channel, context, payload):
        for name in ("phone", "from", "address", "email", "peer", "handle", "sender"):
            value = source.get(name)
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, dict):
                for inner in ("phone", "email", "address", "id", "handle"):
                    if isinstance(value.get(inner), str):
                        found.append(value[inner])
    if isinstance(payload.get("conversationId"), str):
        found.append(payload["conversationId"])
    return found


def contact_key(payload):
    """Stable person for this agent. A turn id or turn URL is not a person."""
    turn_id = str(payload.get("turnId") or "")
    turn_url = str((payload.get("keiki") or {}).get("turnUrl") or "")
    agent = str(payload.get("agentId") or "")
    usable = []
    for raw in _candidates(payload):
        text = _canon(raw)
        if not text or text == turn_id or (turn_url and text in turn_url):
            continue
        usable.append(text)
    contact = usable[0] if usable else _canon(payload.get("conversationId")) or turn_id
    return (agent, contact)


def _chat_path(key):
    digest = hashlib.sha256(f"{key[0]}\n{key[1]}".encode()).hexdigest()
    return os.path.join(_chat_dir(), digest + ".json")


def _load_chat(key):
    with _lock:
        cached = _states.get(key)
    if isinstance(cached, dict):
        return cached
    try:
        with open(_chat_path(key), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(state, dict):
        return {}
    with _lock:
        _states[key] = state
    return state


def _save_chat(key, state):
    path = _chat_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(temp, path)
    with _lock:
        _states.pop(key, None)
        _states[key] = state
        while len(_states) > MAX_CONVERSATIONS:
            _states.pop(next(iter(_states)))


def _inbound(payload):
    parts = []
    for message in payload.get("messages") or []:
        if not isinstance(message, dict) or message.get("silent"):
            continue
        raw = message.get("text") if isinstance(message.get("text"), str) else ""
        if not raw.strip() and isinstance(message.get("content"), str):
            raw = message["content"]
        raw = re.sub(r"^\[Message;[^\]]*\]\s*", "", raw).strip()
        if raw:
            parts.append(raw)
    return "\n".join(parts).strip()


def _say(turn_url, token, text, key):
    text = " ".join(str(text or "").split())
    if not text:
        return
    for index in range(0, len(text), MAX_TEXT):
        chunk = text[index : index + MAX_TEXT]
        suffix = "" if index == 0 else f":{index}"
        _post(f"{turn_url}/messages", token, {"text": chunk, "idempotencyKey": f"{key}{suffix}"})


def _signal(turn_url, token, route):
    try:
        _post(f"{turn_url}/{route}", token, {})
    except Exception:
        logger.info("keiki %s was not accepted", route)


def _share_url(state):
    from ..live_report import ready
    from ..results import save_result
    from .access import public_base

    if not ready(state):
        return ""
    token = save_result(state)
    base = public_base()
    return f"{base}/r/{token}" if base else f"/r/{token}"


def run_turn(payload, token):
    from ..chat_send import user_chat_send

    with user_chat_send():
        _run_turn(payload, token)


def _run_turn(payload, token):
    turn_url = (payload.get("keiki") or {}).get("turnUrl")
    turn_id = str(payload.get("turnId") or "")
    key = contact_key(payload)
    text = _inbound(payload)
    started = time.monotonic()
    leased = started
    acked = False
    try:
        if text and not payload.get("silent"):
            state = _load_chat(key)
            message = text
            for _step in range(MAX_STEPS):
                if time.monotonic() - started >= TURN_DEADLINE:
                    raise TimeoutError("turn deadline")
                result = _engine(message, state)
                message = ""
                state = result.get("state") or state
                _save_chat(key, state)
                phase = state.get("phase")
                if result.get("next"):
                    if not acked:
                        _say(turn_url, token, ACK, f"{turn_id}:ack")
                        _signal(turn_url, token, "typing")
                        _signal(turn_url, token, "lease")
                        acked = True
                        leased = time.monotonic()
                    elif time.monotonic() - leased >= 60:
                        _signal(turn_url, token, "lease")
                        leased = time.monotonic()
                    continue
                if phase == "done":
                    url = _share_url(state)
                    if url:
                        _say(
                            turn_url,
                            token,
                            f"Your engagement is ready. Here’s the report, deck, and kit: {url} — text me if you want changes.",
                            f"{turn_id}:ready",
                        )
                        _post(f"{turn_url}/complete", token, {"status": "completed"})
                        return
                elif phase in QUESTIONS or not acked:
                    _say(turn_url, token, result.get("reply") or "", f"{turn_id}:ask")
                    _post(f"{turn_url}/complete", token, {"status": "completed"})
                    return
                _say(turn_url, token, SORRY, f"{turn_id}:sorry")
                _post(f"{turn_url}/complete", token, {"status": "failed"})
                return
        _post(f"{turn_url}/complete", token, {"status": "completed"})
    except Exception:
        logger.exception("keiki turn failed")
        try:
            _say(turn_url, token, SORRY, f"{turn_id}:sorry")
            _post(f"{turn_url}/complete", token, {"status": "failed"})
        except Exception:
            logger.exception("keiki complete failed")


@bp.post("/keiki/turn")
def keiki_turn():
    if not _secret():
        return jsonify({"error": "not_configured"}), 503
    raw = request.get_data(cache=True)
    header = request.headers.get("Keiki-Signature", "")
    now = time.time()
    if not verify(raw, header, _secret(), now=now):
        return jsonify({"error": "signature_rejected"}), 401
    if not _fresh(raw, header, now):
        return jsonify({"error": "replayed"}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "bad_turn"}), 400
    expected_agent = os.environ.get("KEIKI_AGENT_ID")
    if expected_agent and payload.get("agentId") != expected_agent:
        return jsonify({"error": "unknown_agent"}), 401
    kind = payload.get("type", "keiki.turn")
    if kind != "keiki.turn":  # arrivals, cancellations, reactions: accept, run nothing
        return jsonify({"ok": True}), 202
    token = request.headers.get("Keiki-Turn-Token", "")
    if not token or not (payload.get("keiki") or {}).get("turnUrl"):
        return jsonify({"error": "bad_turn"}), 400
    threading.Thread(target=run_turn, args=(payload, token), daemon=True).start()
    return jsonify({"ok": True}), 202


SELF_CHECK_SINK = "https://httpbin.org/anything/ai-partner-keiki-self-check"


def self_check(url):
    """POST two turns signed with our own secret to `url` and log only the status codes.

    The turn carries no messages, so the engine never runs; its /complete goes to a public echo
    sink with a dummy token. Nothing reaches Keiki or a real conversation.
    """
    agent = os.environ.get("KEIKI_AGENT_ID", "")
    statuses = {}
    for kind, extra in (("keiki.arrival", {}), ("keiki.turn", {"messages": [], "keiki": {"turnUrl": SELF_CHECK_SINK}})):
        raw = json.dumps({"type": kind, "agentId": agent, "turnId": "self-check", "conversationId": "self-check", **extra}).encode()
        ts = int(time.time())
        signature = hmac.new(_secret().encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
        headers = {"Content-Type": "application/json", "Keiki-Signature": f"t={ts},v1={signature}", "Keiki-Turn-Token": "self-check"}
        try:
            statuses[kind] = requests.post(url, data=raw, headers=headers, timeout=20).status_code
        except requests.RequestException as exc:
            statuses[kind] = type(exc).__name__
    logger.info("keiki self-check %s: %s", url, statuses)
    return statuses


def start_self_check(url, delay=60):
    """Run self_check once, after the new deployment has had time to take traffic."""
    timer = threading.Timer(delay, self_check, args=(url,))
    timer.daemon = True
    timer.start()

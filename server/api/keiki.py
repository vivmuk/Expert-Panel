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
import threading
import time

import requests
from flask import Blueprint, jsonify, request

bp = Blueprint("keiki", __name__)
logger = logging.getLogger(__name__)

MAX_SKEW = 300
MAX_TEXT = 3500
MAX_STEPS = 30  # one engagement is ~13 engine steps; Keiki's turn deadline is 10 minutes
MAX_CONVERSATIONS = 500
_states = {}  # (agentId, conversationId) -> engine state; in-process only, oldest evicted first
_lock = threading.Lock()


def _secret():
    return os.environ.get("KEIKI_HARNESS_SIGNING_SECRET", "")


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


def run_turn(payload, token):
    turn_url = (payload.get("keiki") or {}).get("turnUrl")
    turn_id = payload.get("turnId", "")
    key = (payload.get("agentId"), payload.get("conversationId"))
    text = "\n".join(
        str(m.get("content") or m.get("text") or "") for m in payload.get("messages") or [] if not m.get("silent")
    ).strip()
    try:
        if text and not payload.get("silent"):
            with _lock:
                state = _states.get(key, {})
            for step in range(MAX_STEPS):
                result = _engine(text if step == 0 else "", state)
                state = result.get("state") or state
                with _lock:
                    _states.pop(key, None)
                    _states[key] = state
                    while len(_states) > MAX_CONVERSATIONS:
                        _states.pop(next(iter(_states)))
                reply = (result.get("reply") or "").strip()
                for i in range(0, len(reply), MAX_TEXT):
                    body = {"text": reply[i : i + MAX_TEXT], "idempotencyKey": f"{turn_id}:{step}:{i}"}
                    _post(f"{turn_url}/messages", token, body)
                if not result.get("next"):
                    break
        _post(f"{turn_url}/complete", token, {"status": "completed"})
    except Exception as exc:  # report, never leak details
        logger.exception("keiki turn failed")
        try:
            _post(f"{turn_url}/complete", token, {"status": "failed", "error": type(exc).__name__})
        except Exception:
            logger.exception("keiki complete failed")


@bp.post("/keiki/turn")
def keiki_turn():
    if not _secret():
        return jsonify({"error": "not_configured"}), 503
    raw = request.get_data(cache=True)
    if not verify(raw, request.headers.get("Keiki-Signature", ""), _secret()):
        return jsonify({"error": "signature_rejected"}), 401
    payload = request.get_json(silent=True) or {}
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

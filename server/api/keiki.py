"""Keiki external harness (push mode).

Keiki POSTs a signed `keiki.turn` to /keiki/turn. We verify `Keiki-Signature`
(HMAC-SHA256 over "<t>.<raw body>") with KEIKI_HARNESS_SIGNING_SECRET, answer 202,
run the existing chat engine in a background thread, then reply through
POST {turnUrl}/messages and settle with POST {turnUrl}/complete.
Docs: https://onkeiki.com/docs/external-harness.md
"""

import hashlib
import hmac
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
CHANNELS = ["iMessage", "WhatsApp", "Slack", "SMS", "Telegram", "Teams", "email"]


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


def live_channels():
    raw = os.environ.get("KEIKI_LIVE_CHANNELS", "")
    wanted = {c.strip().lower() for c in raw.split(",") if c.strip()}
    return [c for c in CHANNELS if c.lower() in wanted]


def keiki_strip():
    from html import escape

    live = live_channels()
    soon = [c for c in CHANNELS if c not in live]
    bits = []
    if live:
        bits.append("<b>Live:</b> " + escape(", ".join(live)))
    if soon:
        bits.append("<span>Coming soon:</span> " + escape(", ".join(soon)))
    return (
        '<p class="keiki-strip">Reach AI Partner via <a href="https://onkeiki.com" rel="noopener">Keiki</a> · '
        + " · ".join(bits)
        + "</p>"
    )

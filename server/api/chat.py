import logging
import threading
import time

from flask import Blueprint, Response, jsonify, request

from ..chatjob import WELCOME, handle_turn, load_state, render_report
from ..chatmemory import recall, remember
from ..exa_search import exa_search
from ..harnesskit import build_kit_zip
from ..skillpack import build_pack_zip
from ..uploads import take_uploads
from .chat_page import render_page

logger = logging.getLogger(__name__)
bp = Blueprint("partner_chat", __name__)

WINDOW_SECONDS = 600
TURN_LIMIT = 20
_lock = threading.Lock()
_hits = {}


def allow_in_this_process(chat_id, now=None):
    now = time.time() if now is None else now
    with _lock:
        hits = [stamp for stamp in _hits.get(chat_id, []) if now - stamp < WINDOW_SECONDS]
        if len(hits) >= TURN_LIMIT:
            _hits[chat_id] = hits
            return False
        hits.append(now)
        _hits[chat_id] = hits
        return True


def reset_limits():
    with _lock:
        _hits.clear()


def complete_with_venice(name, messages, schema, max_tokens):
    from ..config import Config
    from ..venice.client import get_client

    model = Config.MODEL_ROLE_DEFAULTS["workchart"] if name == "ChatChart" else Config.MODEL_ROLE_DEFAULTS["expert"]
    return get_client().structured(
        model,
        messages,
        name,
        schema,
        temperature=0.3,
        max_completion_tokens=max_tokens,
    )


def _body():
    raw = request.get_json(force=True, silent=True)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None
    return raw


def _bad(message):
    return jsonify({"error": {"code": "bad_request", "message": message}}), 400


REPLY_SCHEMA = {
    "type": "object",
    "properties": {"response": {"type": "string"}},
    "required": ["response"],
    "additionalProperties": False,
}


@bp.get("/chat")
def chat_page():
    return Response(render_page(WELCOME), mimetype="text/html")


@bp.post("/chat")
def post_root_chat():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    if "state" in raw or "uploads" in raw:
        return post_chat()
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        return _bad("message is required")
    source = raw.get("source") if isinstance(raw.get("source"), str) else ""
    user = message.strip()[:8000]
    if source:
        user = f"Channel: {source}\n\n{user}"
    try:
        data = complete_with_venice(
            "ChatReply",
            [
                {
                    "role": "system",
                    "content": (
                        "You are AI Partner. Answer in one short paragraph and name one next step."
                    ),
                },
                {"role": "user", "content": user},
            ],
            REPLY_SCHEMA,
            500,
        )
    except Exception:
        logger.exception("stateless chat failed")
        return jsonify({"response": "The model call failed. Send the message again."}), 502
    text = str((data or {}).get("response") or "").strip() if isinstance(data, dict) else ""
    if not text:
        return jsonify({"response": "The model returned an empty answer. Send the message again."}), 502
    return jsonify({"response": text})


@bp.post("/api/chat")
def post_chat():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    message = raw.get("message") or ""
    if not isinstance(message, str):
        return _bad("Message must be text.")
    if len(message) > 8000:
        return _bad("Message is too long.")
    state = load_state(raw.get("state"))
    if raw.get("uploads"):
        state["uploads"] = take_uploads(raw.get("uploads"), state.get("uploads") or [])
    if not allow_in_this_process(state["chat_id"]):
        reply = "This chat is sending messages too fast. Wait a few minutes and try again."
        return jsonify(
            {
                "reply": reply,
                "state": state,
                "next": None,
                "error": {"code": "rate", "message": reply},
            }
        ), 429
    try:
        result = handle_turn(state, message, complete_with_venice, recall, remember, exa_search)
    except Exception:
        logger.exception("chat turn failed at phase %s", state.get("phase"))
        reply = "The model call failed. Your earlier answers are still here. Send the message again."
        return jsonify(
            {
                "reply": reply,
                "state": state,
                "next": None,
                "error": {"code": "model", "message": reply},
            }
        ), 502
    status = 429 if result.get("error") and result["error"]["code"] == "budget" else 200
    return jsonify(result), status


@bp.post("/api/chat/kit")
def chat_kit():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    state = load_state(raw.get("state"))
    try:
        blob = build_kit_zip(state)
    except ValueError:
        return jsonify({"error": {"code": "not_ready", "message": "The work chart is not ready yet."}}), 400
    return Response(
        blob,
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=harness-kit.zip"},
    )


@bp.post("/api/chat/skill-pack")
def chat_skill_pack():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    state = load_state(raw.get("state"))
    try:
        blob = build_pack_zip(state)
    except ValueError:
        return jsonify({"error": {"code": "not_ready", "message": "The skill pack is not ready yet."}}), 400
    return Response(
        blob,
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=skill-pack.zip"},
    )


@bp.post("/api/chat/report")
def chat_report():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    state = load_state(raw.get("state"))
    try:
        body = render_report(state)
    except ValueError:
        return jsonify({"error": {"code": "not_ready", "message": "The report is not ready yet."}}), 400
    return Response(
        body,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=report.md"},
    )

import logging
import os
import threading
import time

from flask import Blueprint, Response, jsonify, redirect, request, send_from_directory

from ..artifacts import ArtifactError, generate_artifact
from ..catalog import groups, recommend
from ..chatjob import (
    NOT_CONFIGURED_REPLY,
    WELCOME,
    TurnFailed,
    handle_turn,
    load_state,
    render_report,
)
from ..chatmemory import recall, remember
from ..exa_search import exa_search
from ..harnesskit import build_kit_zip
from ..keys import signing_secrets
from ..skillpack import build_pack_zip
from ..uploads import take_uploads
from ..venice.errors import SPEND_LIMIT_REPLY, out_of_credit
from .chat_page import render_page
from .connect_page import render_connect
from .pages import render_catalog, render_what_you_get

_STATIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

logger = logging.getLogger(__name__)
bp = Blueprint("partner_chat", __name__)

WINDOW_SECONDS = 600
TURN_LIMIT = 20
GLOBAL_LIMIT = 200
MAX_KEYS = 2000
DAY_SECONDS = 86400
_lock = threading.Lock()
_hits = {}
_global = []
_starts = {}

DAILY_LIMIT_REPLY = "This network has started its engagements for today. Continue an open one, or come back tomorrow."


def client_ip():
    """The peer address. ProxyFix in create_app sets it from the hop our proxy appended, never the client's own."""
    return request.remote_addr or "unknown"


def daily_engagements():
    try:
        return max(1, int(os.environ.get("AI_PARTNER_DAILY_ENGAGEMENTS", "5")))
    except ValueError:
        return 5


def admit_engagement(ip, chat_id, now=None):
    """Each new chat_id gets a fresh call budget, so cap how many one IP can open per day."""
    now = time.time() if now is None else now
    with _lock:
        seen = {cid: stamp for cid, stamp in _starts.get(ip, {}).items() if now - stamp < DAY_SECONDS}
        if chat_id not in seen and len(seen) >= daily_engagements():
            _starts[ip] = seen
            return False
        seen.setdefault(chat_id, now)
        _starts[ip] = seen
        if len(_starts) > MAX_KEYS:
            oldest = min(_starts, key=lambda key: max(_starts[key].values(), default=0))
            _starts.pop(oldest, None)
        return True


def allow_in_this_process(ip, now=None):
    now = time.time() if now is None else now
    with _lock:
        _evict(now)
        fresh = [stamp for stamp in _global if now - stamp < WINDOW_SECONDS]
        if len(fresh) >= GLOBAL_LIMIT:
            _global[:] = fresh
            return False
        hits = [stamp for stamp in _hits.get(ip, []) if now - stamp < WINDOW_SECONDS]
        if len(hits) >= TURN_LIMIT:
            _hits[ip] = hits
            return False
        hits.append(now)
        _hits[ip] = hits
        fresh.append(now)
        _global[:] = fresh
        if len(_hits) > MAX_KEYS:
            oldest = min(_hits, key=lambda key: _hits[key][-1] if _hits[key] else 0)
            _hits.pop(oldest, None)
        return True


def _evict(now):
    stale = [key for key, stamps in _hits.items() if not stamps or now - stamps[-1] >= WINDOW_SECONDS]
    for key in stale:
        _hits.pop(key, None)
    if len(_hits) <= MAX_KEYS:
        return
    ranked = sorted(_hits, key=lambda key: _hits[key][-1] if _hits[key] else 0)
    for key in ranked[: len(_hits) - MAX_KEYS]:
        _hits.pop(key, None)


def reset_limits():
    with _lock:
        _hits.clear()
        _global.clear()
        _starts.clear()


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


@bp.get("/app.css")
def app_css():
    return send_from_directory(_STATIC, "app.css")


@bp.get("/favicon.ico")
@bp.get("/favicon-32.png")
@bp.get("/favicon-512.png")
@bp.get("/apple-touch-icon.png")
def favicon():
    return send_from_directory(_STATIC, request.path.rsplit("/", 1)[-1])


@bp.get("/img/<path:name>")
def brand_img(name):
    return send_from_directory(os.path.join(_STATIC, "img"), name)


@bp.get("/voice.js")
def voice_js():
    return send_from_directory(_STATIC, "voice.js")


@bp.get("/motion.js")
def motion_js():
    return send_from_directory(_STATIC, "motion.js")


@bp.get("/chat.js")
def chat_js():
    return send_from_directory(_STATIC, "chat.js")


@bp.get("/onboard.js")
def onboard_js():
    return send_from_directory(_STATIC, "onboard.js")


@bp.get("/report.css")
def report_css():
    return send_from_directory(_STATIC, "report.css")


@bp.get("/report.js")
def report_js():
    return send_from_directory(_STATIC, "report.js")


@bp.get("/deck-embed.js")
def deck_embed_js():
    return send_from_directory(_STATIC, "deck-embed.js")


@bp.get("/voice/<path:name>")
def voice_file(name):
    return send_from_directory(os.path.join(_STATIC, "voice"), name)


@bp.get("/connect")
def connect_page():
    from .access import request_origin

    return Response(render_connect(request_origin()), mimetype="text/html")


@bp.get("/catalog")
def catalog_page():
    return Response(render_catalog(), mimetype="text/html")


@bp.get("/what-you-get")
def what_you_get_page():
    return Response(render_what_you_get(), mimetype="text/html")


@bp.get("/pricing")
def pricing_page():
    return redirect("/connect", code=301)


@bp.get("/chat")
def chat_page():
    from .access import request_origin

    return Response(render_page(WELCOME, request_origin()), mimetype="text/html")


@bp.post("/chat")
def post_root_chat():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    if "state" in raw or "uploads" in raw:
        return post_chat()
    if not allow_in_this_process(client_ip()):
        return jsonify({"response": "This chat is sending messages too fast. Wait a few minutes and try again."}), 429
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        return _bad("message is required")
    source = raw.get("source") if isinstance(raw.get("source"), str) else ""
    from ..chatjob import untrusted

    user = untrusted("Message", message.strip()[:8000])
    if source:
        user = untrusted("Channel", source[:200]) + "\n\n" + user
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
    except Exception as exc:
        logger.exception("stateless chat failed")
        if out_of_credit(exc):
            return jsonify({"response": SPEND_LIMIT_REPLY}), 503
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
    incoming = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    if raw.get("uploads"):
        incoming = dict(incoming)
        incoming["uploads"] = take_uploads(raw.get("uploads"), incoming.get("uploads") or [])
    if not signing_secrets():
        return _refuse(incoming, "not_configured", NOT_CONFIGURED_REPLY, 503)
    if not allow_in_this_process(client_ip()):
        return _refuse(incoming, "rate", "This chat is sending messages too fast. Wait a few minutes and try again.", 429)
    incoming = {**incoming, "chat_id": load_state(incoming)["chat_id"]}
    if not admit_engagement(client_ip(), incoming["chat_id"]):
        return _refuse(incoming, "daily_limit", DAILY_LIMIT_REPLY, 429)
    try:
        result = handle_turn(incoming, message, complete_with_venice, recall, remember, exa_search)
    except Exception as exc:
        state = exc.state if isinstance(exc, TurnFailed) else load_state(incoming)
        logger.exception("chat turn failed at phase %s", state.get("phase"))
        if out_of_credit(exc):
            return jsonify(
                {
                    "reply": SPEND_LIMIT_REPLY,
                    "state": state,
                    "next": None,
                    "error": {"code": "spend_limit", "message": SPEND_LIMIT_REPLY},
                }
            ), 503
        reply = "The model call failed. Your earlier answers are still here. Send the message again."
        return jsonify(
            {
                "reply": reply,
                "state": state,
                "next": None,
                "error": {"code": "model", "message": reply},
            }
        ), 502
    code = (result.get("error") or {}).get("code")
    status = {"tamper": 400, "budget": 429, "not_configured": 503}.get(code, 200)
    return jsonify(result), status


def _refuse(incoming, code, reply, status):
    if status == 429:
        logger.warning("chat %s limit for %s", code, client_ip())
    return jsonify({"reply": reply, "state": load_state(incoming), "next": None, "error": {"code": code, "message": reply}}), status


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


@bp.get("/api/catalog")
def catalog_json():
    return jsonify({"groups": groups(), "recommend_default": recommend({})})


@bp.post("/api/chat/artifact")
def chat_artifact():
    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    artifact_id = raw.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _bad("artifact_id is required")
    if not allow_in_this_process(client_ip()):
        return jsonify({"error": {"code": "rate", "message": "This chat is sending messages too fast. Wait a few minutes and try again."}}), 429
    incoming = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    try:
        result = generate_artifact(incoming, artifact_id.strip(), complete_with_venice)
    except ArtifactError as exc:
        status = 503 if exc.code == "not_configured" else 400 if exc.code in ("unknown", "tamper", "limit", "budget") else 502
        return jsonify({"error": {"code": exc.code, "message": str(exc)}}), status
    except Exception as exc:
        logger.exception("artifact %s failed", artifact_id)
        if out_of_credit(exc):
            return jsonify({"error": {"code": "spend_limit", "message": SPEND_LIMIT_REPLY}}), 503
        return jsonify({"error": {"code": "model", "message": "The model call failed. Try again."}}), 502
    return jsonify(result)


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

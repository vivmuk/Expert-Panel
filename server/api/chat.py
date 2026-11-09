import logging
import os
import threading
import time

from flask import Blueprint, Response, jsonify, redirect, request, send_from_directory

from ..artifact_doc import as_html
from ..artifacts import ArtifactError, generate_artifact
from ..catalog import by_id, groups, recommend
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
from ..live_report import deliverables, live_demo
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
TURN_LIMIT = 24
GLOBAL_LIMIT = 200
MAX_KEYS = 2000
DAY_SECONDS = 86400
_lock = threading.Lock()
_hits = {}
_global = []
_starts = {}

DAILY_LIMIT_REPLY = "This network has started its engagements for today. Continue an open one, or come back tomorrow."
RATE_REPLY = "This chat is sending messages too fast. Wait a few minutes and try again."


def client_ip_header():
    """Railway and Vercel set X-Real-IP at their edge, replacing any value the client sent. Railway documents no X-Forwarded-For."""
    configured = os.environ.get("AI_PARTNER_CLIENT_IP_HEADER", "").strip()
    if configured:
        return configured
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("VERCEL"):
        return "X-Real-IP"
    return ""


def client_ip():
    """The edge-set client header where the platform has one, else the peer that ProxyFix took from the last hop."""
    header = client_ip_header()
    value = request.headers.get(header, "").split(",")[-1].strip() if header else ""
    return value or request.remote_addr or "unknown"


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
    from ..exposure import current, describe_venice

    active = current()
    if active is None:
        del name, messages, schema, max_tokens
        from ..spendguard import refuse_paid

        refuse_paid()
    transport, bound = active.consume(describe_venice(name, messages, schema, max_tokens))
    return transport.venice(bound)


complete_with_venice._spend_enforced = True


def _body():
    """A JSON object, {} when the body is empty, or None when the body is not an object."""
    raw_bytes = request.get_data(cache=True)
    if not raw_bytes.strip():
        return {}
    raw = request.get_json(force=True, silent=True)
    if not isinstance(raw, dict):
        return None
    return raw


def spend_block(raw):
    """Shared gate for a model call. Returns (code, message, chat_id).

    code is None when the call may proceed. chat_id is the id the caller must
    pass into the job, so the daily cap and the call budget name one engagement.
    A missing id counts as a new engagement.
    """
    ip = client_ip()
    if not allow_in_this_process(ip):
        return "rate", RATE_REPLY, None
    chat_id = load_state(raw if isinstance(raw, dict) else {})["chat_id"]
    if not admit_engagement(ip, chat_id):
        return "daily_limit", DAILY_LIMIT_REPLY, None
    return None, None, chat_id


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


@bp.get("/history.js")
def history_js():
    return send_from_directory(_STATIC, "history.js")


@bp.get("/onboard.js")
def onboard_js():
    return send_from_directory(_STATIC, "onboard.js")


@bp.get("/keiki.js")
def keiki_js():
    return send_from_directory(_STATIC, "keiki.js")


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
    if not signing_secrets():
        return jsonify({"response": NOT_CONFIGURED_REPLY}), 503
    if not allow_in_this_process(client_ip()):
        return jsonify({"response": RATE_REPLY}), 429
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
        from ..spendguard import SpendClosed

        if isinstance(exc, SpendClosed):
            return jsonify({"response": exc.message, "error": {"code": exc.code, "message": exc.message}}), 403
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
    code, limit_message, chat_id = spend_block(incoming)
    if code:
        return _refuse(incoming, code, limit_message, 429)
    incoming = {**incoming, "chat_id": chat_id}
    scoped_recall, scoped_remember = _memory_for(raw)
    try:
        result = handle_turn(incoming, message, complete_with_venice, scoped_recall, scoped_remember, exa_search)
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
    status = {
        "tamper": 400,
        "budget": 429,
        "not_configured": 503,
        "spend_ledger_unavailable": 403,
        "currency_bound_unavailable": 403,
        "calculated_price_unavailable": 403,
        "calculated_ceiling_exceeded": 403,
        "phase_uncertain": 409,
        "paid_path_blocked": 403,
    }.get(code, 200)
    return jsonify(result), status


def _memory_for(raw):
    """Web chat sends a browser visitor id. Invalid ids are ignored inside chatmemory."""
    visitor_id = raw.get("visitor_id") if isinstance(raw.get("visitor_id"), str) else None
    has_history = raw.get("has_history") is True

    def scoped_recall(chat_id, query):
        return recall(chat_id, query, visitor_id=visitor_id, has_history=has_history)

    def scoped_remember(chat_id, content):
        return remember(chat_id, content, visitor_id=visitor_id)

    return scoped_recall, scoped_remember


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
    incoming = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    code, message, chat_id = spend_block(incoming)
    if code:
        return jsonify({"error": {"code": code, "message": message}}), 429
    incoming = {**incoming, "chat_id": chat_id}
    try:
        result = generate_artifact(incoming, artifact_id.strip(), complete_with_venice)
    except ArtifactError as exc:
        status = 503 if exc.code == "not_configured" else 400 if exc.code in ("unknown", "tamper", "limit", "budget") else 403 if exc.code in (
            "spend_ledger_unavailable",
            "currency_bound_unavailable",
            "calculated_price_unavailable",
            "calculated_ceiling_exceeded",
            "phase_uncertain",
            "paid_path_blocked",
        ) else 502
        return jsonify({"error": {"code": exc.code, "message": str(exc)}}), status
    except Exception as exc:
        from ..spendguard import SpendClosed

        if isinstance(exc, SpendClosed):
            return jsonify({"error": {"code": exc.code, "message": exc.message}}), 403
        logger.exception("artifact %s failed", artifact_id)
        if out_of_credit(exc):
            return jsonify({"error": {"code": "spend_limit", "message": SPEND_LIMIT_REPLY}}), 503
        return jsonify({"error": {"code": "model", "message": "The model call failed. Try again."}}), 502
    result["html"] = as_html(by_id(artifact_id.strip())["title"], result["markdown"])
    return jsonify(result)


@bp.post("/api/chat/view")
def chat_view():
    from .access import request_origin
    from .demos import report_fragment

    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    try:
        demo = live_demo(raw.get("state"))
        files = deliverables(raw.get("state"), request_origin())
    except ValueError:
        return jsonify({"error": {"code": "not_ready", "message": "The report is not ready yet."}}), 400
    catalog = []
    for key, text in load_state(raw.get("state")).get("artifacts", {}).items():
        title = by_id(key)["title"]
        catalog.append({"id": f"catalog:{key}", "title": title, "html": as_html(title, text), "markdown": text})
    return jsonify({"report": report_fragment(demo), "deliverables": files, "catalog": catalog})


@bp.post("/api/chat/deck.pptx")
def chat_deck():
    from ..deck_pptx import build_pptx

    raw = _body()
    if raw is None:
        return _bad("Send a JSON object.")
    try:
        blob = build_pptx(raw.get("state"))
    except ValueError:
        return jsonify({"error": {"code": "not_ready", "message": "The deck is not ready yet."}}), 400
    return Response(
        blob,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=client-deck.pptx"},
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

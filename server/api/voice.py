"""Voice guide. Audio is not logged."""
from flask import Blueprint, Response, jsonify, request

from ..spendguard import SpendClosed
from ..venice.client import VeniceError
from .chat import allow_in_this_process, client_ip

bp = Blueprint("voice", __name__)
MAX_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 30

@bp.post("/api/voice/turn")
def turn():
    if not allow_in_this_process(client_ip()):
        return jsonify({"error": {"code": "rate", "message": "Too many voice turns."}}), 429
    upload = request.files.get("audio")
    if upload is None:
        return jsonify({"error": {"code": "bad_request", "message": "Attach an audio file."}}), 400
    duration = request.form.get("duration")
    if duration and _seconds(duration) > MAX_SECONDS:
        return jsonify({"error": {"code": "bad_request", "message": "Audio is limited to 30 seconds."}}), 400
    blob = upload.read(MAX_BYTES + 1)
    if len(blob) > MAX_BYTES:
        return jsonify({"error": {"code": "bad_request", "message": "Audio is limited to 2MB."}}), 400
    if not blob:
        return jsonify({"error": {"code": "bad_request", "message": "The recording was empty."}}), 400
    try:
        heard = _transcribe(blob, upload.mimetype or "audio/webm")
    except VeniceError:
        return jsonify({"error": {"code": "model", "message": "Transcription failed."}}), 502
    except SpendClosed as exc:
        return jsonify({"error": {"code": exc.code, "message": exc.message}}), 403
    return _plan_and_speak(heard)


@bp.post("/api/voice/plan")
def plan():
    if not allow_in_this_process(client_ip()):
        return jsonify({"error": {"code": "rate", "message": "Too many voice turns."}}), 429
    body = request.get_json(silent=True) or {}
    heard = " ".join(str(body.get("text") or "").split())[:500]
    if not heard:
        return jsonify({"error": {"code": "bad_request", "message": "text is required"}}), 400
    return _plan_and_speak(heard)


def _plan_and_speak(heard):
    try:
        action = _planned(heard)
    except SpendClosed as exc:
        return jsonify({"error": {"code": exc.code, "message": exc.message}}), 403
    action = action or {"action": "answer", "text": "I can open Chat, Demos, the Deck, Catalog, or Connect.", "say": "I can open Chat, Demos, the Deck, Catalog, or Connect."}
    try:
        audio = _speak(action["say"])
    except SpendClosed as exc:
        return jsonify({"error": {"code": exc.code, "message": exc.message}}), 403
    except VeniceError:
        audio = b""
    payload = {"heard": heard, "action": action, "captions": action["say"]}
    if audio:
        payload["audio_mpeg_base64"] = __import__("base64").b64encode(audio).decode()
    return jsonify(payload)


def _voice_or_refuse(operation, text):
    from ..exposure import current, describe_voice
    from ..spendguard import refuse_paid

    active = current()
    if active is None:
        refuse_paid()
    transport, bound = active.consume(describe_voice(operation, text))
    return transport.voice(bound)


def _planned(heard):
    return _voice_or_refuse("plan", heard)


def _transcribe(blob, mime):
    return _voice_or_refuse("transcribe", {"blob": blob, "mime": mime})


def _speak(text):
    return _voice_or_refuse("speak", text)


def _seconds(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return MAX_SECONDS + 1

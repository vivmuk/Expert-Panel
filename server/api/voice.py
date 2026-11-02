"""Voice guide. Audio is not logged."""
import os

import requests
from flask import Blueprint, Response, jsonify, request

from ..venice.client import VeniceClient, VeniceError
from ..voice_actions import WELCOME, validate_action
from .chat import allow_in_this_process, client_ip

bp = Blueprint("voice", __name__)
MAX_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 30

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "page": {"type": "string"},
        "section": {"type": "string"},
        "text": {"type": "string"},
        "depth": {"type": "string"},
        "slug": {"type": "string"},
        "id": {"type": "string"},
        "say": {"type": "string"},
    },
    "required": ["action", "say"],
    "additionalProperties": False,
}


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
    action = _planned(heard) or {"action": "answer", "text": "I can open Chat, Demos, the Deck, Catalog, or Connect.", "say": "I can open Chat, Demos, the Deck, Catalog, or Connect."}
    try:
        audio = _speak(action["say"])
    except VeniceError:
        audio = b""
    payload = {"heard": heard, "action": action, "captions": action["say"]}
    if audio:
        payload["audio_mpeg_base64"] = __import__("base64").b64encode(audio).decode()
    return jsonify(payload)


def _planned(heard):
    system = (
        "Clean filler words and mis-hearings, then pick exactly one action. "
        "Actions: navigate(page), scroll_to(section), fill_problem(text), set_depth(strategy|full), "
        "start_engagement, open_demo(slug maritime|keiki|orchid), copy_snippet(id), answer(text). "
        "Pages: /chat /demos /demos/maritime /demos/keiki /demos/orchid /deck /catalog /connect. "
        "Sections: hero demos catalog connect artifacts steps. "
        "Put the spoken reply in say. Return JSON only."
    )
    try:
        data = VeniceClient().structured(
            os.environ.get("MODEL_VOICE_CLEAN", "mercury-3"),
            [{"role": "system", "content": system}, {"role": "user", "content": heard}],
            "VoiceAction",
            PLAN_SCHEMA,
            temperature=0,
            max_completion_tokens=300,
        )
    except VeniceError:
        return None
    return validate_action(data)


def _transcribe(blob, mime):
    key = os.environ.get("VENICE_API_KEY", "")
    base = os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1").rstrip("/")
    response = requests.post(
        base + "/audio/transcriptions",
        headers={"Authorization": f"Bearer {key}"},
        files={"file": ("turn.webm", blob, mime)},
        data={"model": os.environ.get("STT_MODEL", "stt-xai-v1")},
        timeout=60,
    )
    if response.status_code >= 400:
        raise VeniceError(f"HTTP {response.status_code} from /audio/transcriptions", response.status_code, response.text[:200])
    payload = response.json()
    return " ".join(str(payload.get("text") or "").split())[:500]


def _speak(text):
    key = os.environ.get("VENICE_API_KEY", "")
    base = os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1").rstrip("/")
    response = requests.post(
        base + "/audio/speech",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.environ.get("TTS_MODEL", "tts-xai-v1"),
            "voice": os.environ.get("TTS_VOICE", "carina"),
            "input": text[:400],
        },
        timeout=60,
    )
    if response.status_code >= 400:
        raise VeniceError(f"HTTP {response.status_code} from /audio/speech", response.status_code, response.text[:200])
    return response.content


def _seconds(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return MAX_SECONDS + 1

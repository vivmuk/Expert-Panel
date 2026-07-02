"""Brand Studio: the app generates its own watercolor artwork via Venice image
models, caches it in DATA_DIR/branding, and serves it to the frontend. Assets
are generated lazily in a background thread (first visit) and can be
regenerated on demand from Settings."""
import base64
import logging
import os
import threading
import time

from flask import Blueprint, jsonify, request, send_from_directory

from ..config import Config
from ..venice.client import get_client
from ..venice.models import get_catalog

logger = logging.getLogger(__name__)
bp = Blueprint("branding", __name__)

STYLE = (
    "Elegant professional watercolor illustration, soft translucent washes of deep indigo, "
    "teal and warm gold on bright white paper, fine gold constellation lines and small stars, "
    "minimalist composition with generous white space, calm and trustworthy mood, "
    "high quality, no text, no letters, no watermark"
)

SLOTS = {
    "hero": f"{STYLE}. A sweeping constellation of golden stars joined by fine indigo lines rising over soft indigo and teal watercolor clouds, wide banner composition.",
    "deep_dive": f"{STYLE}. A brass telescope on a tripod pointed at a small constellation of stars.",
    "red_team": f"{STYLE}. Two chess knights facing each other over a subtle star field.",
    "quick_pulse": f"{STYLE}. Concentric radar pulse rings radiating from a bright star.",
    "board_meeting": f"{STYLE}. A round boardroom table with chairs seen from above, a constellation reflected on its surface.",
    "workchart": f"{STYLE}. A flowing indigo river splitting into two branching paths among small stars.",
    "scenario_planning": f"{STYLE}. A path forking into three glowing trails through a field of stars.",
    "due_diligence": f"{STYLE}. A magnifying glass hovering over layered paper documents with tiny stars.",
    "ai_opportunity_scan": f"{STYLE}. A gold lightning bolt striking through a constellation.",
    "digital_twin": f"{STYLE}. Two mirrored translucent orbs connected by threads of starlight.",
}

_generating = set()
_lock = threading.Lock()


def _dir():
    path = os.path.join(Config.DATA_DIR, "branding")
    os.makedirs(path, exist_ok=True)
    return path


def _path(slot):
    return os.path.join(_dir(), f"{slot}.webp")


def _resolve_image_model(requested=None):
    catalog = get_catalog()
    image_models = catalog.image_models()
    ids = [m.get("id") for m in image_models]
    for candidate in (requested, Config.MODEL_ROLE_DEFAULTS.get("image")):
        if candidate and candidate in ids:
            return candidate
    if not ids:
        raise RuntimeError("No Venice image models available")
    return ids[0]


def _generate_slot(slot, prompt=None, model=None):
    client = get_client()
    resolved = _resolve_image_model(model)
    aspect_ratio = "16:9" if slot == "hero" else "4:3"
    result = client.generate_image(
        prompt or SLOTS[slot], model=resolved, aspect_ratio=aspect_ratio
    )
    images = result.get("images") or []
    if not images:
        raise RuntimeError(f"No image returned for slot {slot}: {str(result)[:200]}")
    data = images[0]
    if isinstance(data, str) and data.startswith("data:"):
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    with open(_path(slot), "wb") as f:
        f.write(raw)
    logger.info("Brand asset generated: %s via %s (%d bytes)", slot, resolved, len(raw))


def _ensure_missing_async(slots=None, model=None):
    todo = [s for s in (slots or SLOTS) if s in SLOTS and not os.path.exists(_path(s))]
    with _lock:
        todo = [s for s in todo if s not in _generating]
        _generating.update(todo)
    if not todo:
        return []

    def worker():
        # Space out requests and stop after repeated failures so a broken
        # payload or model can't trip Venice's failed-attempts rate limit.
        consecutive_failures = 0
        for i, slot in enumerate(todo):
            try:
                if consecutive_failures >= 3:
                    logger.error("Brand Studio aborting after %d consecutive failures", consecutive_failures)
                    break
                if i > 0:
                    time.sleep(2)
                _generate_slot(slot, model=model)
                consecutive_failures = 0
            except Exception:
                consecutive_failures += 1
                logger.exception("Brand asset generation failed for %s", slot)
        with _lock:
            for slot in todo:
                _generating.discard(slot)

    threading.Thread(target=worker, daemon=True, name="brand-studio").start()
    return todo


@bp.get("/branding/assets")
def assets():
    out = {}
    for slot in SLOTS:
        exists = os.path.exists(_path(slot))
        with _lock:
            busy = slot in _generating
        out[slot] = {
            "url": f"/api/branding/asset/{slot}.webp" if exists else None,
            "generating": busy,
        }
    return jsonify(out)


@bp.post("/branding/ensure")
def ensure():
    started = _ensure_missing_async()
    return jsonify({"started": started})


@bp.post("/branding/generate")
def regenerate():
    """Force-regenerate one slot (or all) — used by the Settings Brand Studio."""
    data = request.get_json(force=True, silent=True) or {}
    slot = data.get("slot")
    slots = [slot] if slot in SLOTS else list(SLOTS)
    for s in slots:
        try:
            os.remove(_path(s))
        except FileNotFoundError:
            pass
    started = _ensure_missing_async(slots, model=data.get("model"))
    return jsonify({"started": started})


@bp.get("/branding/asset/<path:filename>")
def asset(filename):
    response = send_from_directory(_dir(), filename, max_age=3600)
    return response

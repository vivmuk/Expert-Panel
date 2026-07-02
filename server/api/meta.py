"""Meta endpoints: live models, modes, cost estimates, branding art."""
import logging

from flask import Blueprint, jsonify, request

from ..modes import MODE_REGISTRY
from ..pipeline.estimate import estimate_run
from ..venice.client import get_client
from ..venice.models import get_catalog

logger = logging.getLogger(__name__)
bp = Blueprint("meta", __name__)


@bp.get("/models")
def list_models():
    try:
        return jsonify(get_catalog().summary())
    except Exception as exc:
        logger.exception("Model listing failed")
        return jsonify({"error": {"code": "venice_unavailable", "message": str(exc)}}), 502


@bp.get("/modes")
def list_modes():
    return jsonify([spec.to_public() for spec in MODE_REGISTRY.values()])


@bp.post("/estimate")
def estimate():
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "deep_dive")
    panel_size = int(data.get("panelSize", 20))
    try:
        return jsonify(estimate_run(mode, panel_size, data.get("models") or {}))
    except Exception as exc:
        logger.exception("Estimate failed")
        return jsonify({"error": {"code": "estimate_failed", "message": str(exc)}}), 500


@bp.post("/branding/generate")
def branding_generate():
    """Regenerate constellation brand art via Venice image models."""
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("prompt") or (
        "Minimalist deep-space galaxy artwork: sparse constellation of fine glowing stars "
        "connected by thin luminous lines on a near-black indigo sky, subtle nebula haze, "
        "elegant, high contrast, no text, flat vector-like style"
    )
    try:
        result = get_client().generate_image(
            prompt,
            model=data.get("model"),
            width=int(data.get("width", 1280)),
            height=int(data.get("height", 720)),
        )
        return jsonify(result)
    except Exception as exc:
        logger.exception("Branding generation failed")
        return jsonify({"error": {"code": "image_failed", "message": str(exc)}}), 502

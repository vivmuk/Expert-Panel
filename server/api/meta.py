"""Meta endpoints: live models, modes, cost estimates, branding art."""
import logging

from flask import Blueprint, jsonify, request

from ..modes import MODE_REGISTRY
from ..pipeline.estimate import estimate_run
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



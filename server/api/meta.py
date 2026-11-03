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
    except Exception:
        logger.exception("Model listing failed")
        return jsonify({"error": {"code": "venice_unavailable", "message": "The model list is unavailable right now."}}), 502


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
    except Exception:
        logger.exception("Estimate failed")
        return jsonify({"error": {"code": "estimate_failed", "message": "The estimate could not be computed."}}), 500



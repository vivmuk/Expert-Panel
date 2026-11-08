"""Meta endpoints: modes, and closed model-list and estimate routes.

The model list and the estimate both read the live Venice catalog. This
change does not reserve a price for that read, so both routes refuse before
calling it. A cached catalog is not used as a price.
"""
from flask import Blueprint, jsonify

from ..modes import MODE_REGISTRY
from ..spendguard import CLOSED

bp = Blueprint("meta", __name__)


def _closed():
    return jsonify({
        "error": {
            "code": "paid_path_blocked",
            "message": CLOSED["paid_path_blocked"],
        }
    }), 403


@bp.get("/models")
def list_models():
    return _closed()


@bp.get("/modes")
def list_modes():
    return jsonify([spec.to_public() for spec in MODE_REGISTRY.values()])


@bp.post("/estimate")
def estimate():
    return _closed()



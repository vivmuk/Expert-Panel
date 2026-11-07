from flask import Blueprint, jsonify, request

from ..db import engagements as store
from .access import require_partner_key

bp = Blueprint("engagements", __name__)

# Every partner key sees this one database. The key is not an owner id.
_LIMIT_DEFAULT = 50
_LIMIT_MAX = 200
_OFFSET_MAX = 1_000_000


def _bad_page():
    return jsonify({"error": {"code": "bad_request", "message": "limit and offset must be whole numbers in range."}}), 400


def _page_number(name, default, upper):
    raw = request.args.get(name)
    if raw is None:
        return default
    if len(raw) > 7 or not raw.isdigit():
        return None
    value = int(raw)
    if name == "limit" and value < 1:
        return None
    if value > upper:
        return upper if name == "limit" else None
    return value


@bp.get("/engagements")
def list_engagements():
    denied = require_partner_key()
    if denied:
        return denied
    limit = _page_number("limit", _LIMIT_DEFAULT, _LIMIT_MAX)
    offset = _page_number("offset", 0, _OFFSET_MAX)
    if limit is None or offset is None:
        return _bad_page()
    return jsonify(
        store.list_engagements(
            mode=request.args.get("mode"),
            query=request.args.get("q"),
            limit=limit,
            offset=offset,
        )
    )


@bp.get("/engagements/<int:engagement_id>")
def get_engagement(engagement_id):
    denied = require_partner_key()
    if denied:
        return denied
    engagement = store.get_engagement(engagement_id)
    if not engagement:
        return jsonify({"error": {"code": "not_found", "message": "Engagement not found"}}), 404
    return jsonify(engagement)


@bp.get("/engagements/<int:engagement_id>/revisions/<int:rev>")
def get_revision(engagement_id, rev):
    denied = require_partner_key()
    if denied:
        return denied
    revision = store.get_revision(engagement_id, rev)
    if not revision:
        return jsonify({"error": {"code": "not_found", "message": "Revision not found"}}), 404
    return jsonify(revision)


@bp.patch("/engagements/<int:engagement_id>")
def rename(engagement_id):
    denied = require_partner_key()
    if denied:
        return denied
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": {"code": "bad_request", "message": "title is required"}}), 400
    store.rename_engagement(engagement_id, title)
    return jsonify({"ok": True})


@bp.delete("/engagements/<int:engagement_id>")
def delete(engagement_id):
    denied = require_partner_key()
    if denied:
        return denied
    store.delete_engagement(engagement_id)
    return jsonify({"ok": True})

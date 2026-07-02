from flask import Blueprint, jsonify, request

from ..db import engagements as store

bp = Blueprint("engagements", __name__)


@bp.get("/engagements")
def list_engagements():
    return jsonify(
        store.list_engagements(
            mode=request.args.get("mode"),
            query=request.args.get("q"),
            limit=min(int(request.args.get("limit", 50)), 200),
            offset=int(request.args.get("offset", 0)),
        )
    )


@bp.get("/engagements/<int:engagement_id>")
def get_engagement(engagement_id):
    engagement = store.get_engagement(engagement_id)
    if not engagement:
        return jsonify({"error": {"code": "not_found", "message": "Engagement not found"}}), 404
    return jsonify(engagement)


@bp.get("/engagements/<int:engagement_id>/revisions/<int:rev>")
def get_revision(engagement_id, rev):
    revision = store.get_revision(engagement_id, rev)
    if not revision:
        return jsonify({"error": {"code": "not_found", "message": "Revision not found"}}), 404
    return jsonify(revision)


@bp.patch("/engagements/<int:engagement_id>")
def rename(engagement_id):
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": {"code": "bad_request", "message": "title is required"}}), 400
    store.rename_engagement(engagement_id, title)
    return jsonify({"ok": True})


@bp.delete("/engagements/<int:engagement_id>")
def delete(engagement_id):
    store.delete_engagement(engagement_id)
    return jsonify({"ok": True})

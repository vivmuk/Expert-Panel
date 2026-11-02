"""Serve the built React app (web/dist) with SPA fallback."""
import os

from flask import Blueprint, abort, jsonify, redirect, send_from_directory

bp = Blueprint("static_serve", __name__)

_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist"))


def _redirect_home():
    flag = os.environ.get("APP_HOME_REDIRECT", "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


@bp.get("/")
@bp.get("/<path:path>")
def serve(path="index.html"):
    if path == "api" or path.startswith("api/"):
        return jsonify({"error": {"code": "not_found", "message": "Not found."}}), 404
    if path in ("", "index.html") and _redirect_home():
        return redirect("/chat")
    if os.path.isdir(_DIST):
        if os.path.isfile(os.path.join(_DIST, path)):
            return send_from_directory(_DIST, path)
        if not _redirect_home():
            return send_from_directory(_DIST, "index.html")
    abort(404)

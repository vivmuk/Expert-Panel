"""Serve the built React app (web/dist) with SPA fallback."""
import os

from flask import Blueprint, redirect, send_from_directory

bp = Blueprint("static_serve", __name__)

_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist"))


@bp.get("/")
@bp.get("/<path:path>")
def serve(path="index.html"):
    if os.environ.get("VERCEL"):
        if path in ("", "index.html"):
            return redirect("/chat")
        return ("Not found", 404)
    full = os.path.join(_DIST, path)
    if os.path.isfile(full):
        return send_from_directory(_DIST, path)
    return send_from_directory(_DIST, "index.html")

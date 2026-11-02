import os

from flask import Blueprint, send_from_directory

bp = Blueprint("deck", __name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "deck"))


@bp.get("/deck")
@bp.get("/deck/")
def deck_index():
    return send_from_directory(ROOT, "index.html")


@bp.get("/deck/<path:name>")
def deck_file(name):
    return send_from_directory(ROOT, name)

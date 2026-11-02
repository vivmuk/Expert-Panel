import os

from flask import Blueprint, send_from_directory

from ..icons import icon
from .pages import DECK_EMBED_SCRIPT, deck_embed, page_head, shell

bp = Blueprint("deck", __name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "deck"))


def frameable(resp):
    """Decks are embedded on our own pages, so allow same-origin framing and nothing else."""
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return resp


@bp.get("/deck")
@bp.get("/deck/")
def deck_index():
    return frameable(send_from_directory(ROOT, "index.html"))


@bp.get("/deck/<path:name>")
def deck_file(name):
    return frameable(send_from_directory(ROOT, name))


@bp.get("/about")
def about():
    actions = (
        '<div class="hero-actions">'
        f'<a class="btn primary" href="/chat">{icon("message-circle")}Start an engagement</a>'
        f'<a class="btn ghost" href="/connect">{icon("plug")}Connect your own agent</a>'
        "</div>"
    )
    body = page_head(
        "About AI Partner",
        "Your team directs. <em>AI Partner agents</em> do the work.",
        "Company teams describe a business problem. AI Partner agents research the public record, a panel of 20 AI experts "
        "debates it, and your team keeps the Top 5 moves, the work chart and the harness kit. The deck below is the thesis.",
        actions,
    ) + deck_embed(
        "/deck",
        "AI Partner · The First 1,000 deck",
        "The First 1,000",
        kicker="The thesis deck",
        lede="From the invoice to the resident model, in one deck.",
    )
    return shell("About · AI Partner", "/about", f'<div class="about-page">{body}</div>', scripts=DECK_EMBED_SCRIPT)

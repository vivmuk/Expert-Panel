"""Public, unlisted page for one finished engagement."""
from flask import Blueprint, Response

from ..deck_pptx import build_pptx
from ..harnesskit import build_kit_zip
from ..live_report import BUILDERS, live_demo, ready
from ..chatjob import render_report
from ..results import load_result
from ..skillpack import build_pack_zip
from .demos import report_fragment
from .pages import not_found_page, shell

bp = Blueprint("results", __name__)

_FILES = {
    "report.md": ("text/markdown", "report.md"),
    "deck.pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "client-deck.pptx"),
    "kit.zip": ("application/zip", "harness-kit.zip"),
    "skill-pack.zip": ("application/zip", "skill-pack.zip"),
}


def _missing():
    return not_found_page(), 404, {"Content-Type": "text/html; charset=utf-8"}


def _state(token):
    state = load_result(token)
    if not state or not ready(state):
        return None
    return state


@bp.get("/r/<token>")
@bp.get("/r/<token>/<name>")
def results_page(token, name=None):
    state = _state(token)
    if state is None:
        return _missing()
    if name in BUILDERS:
        return Response(BUILDERS[name](state, f"/r/{token}"), mimetype="text/html")
    if name in _FILES:
        try:
            body, mimetype, filename = _file(state, name)
        except ValueError:
            return _missing()
        return Response(body, mimetype=mimetype, headers={"Content-Disposition": f"attachment; filename={filename}"})
    if name:
        return _missing()
    demo = live_demo(state)
    demo["share"] = f"/r/{token}"
    downloads = (
        f'<div class="hero-actions">'
        f'<a class="btn primary" href="/r/{token}/report.md">Report</a>'
        f'<a class="btn ghost" href="/r/{token}/deck.pptx">Client deck</a>'
        f'<a class="btn ghost" href="/r/{token}/kit.zip">Harness kit</a>'
        f'<a class="btn ghost" href="/r/{token}/skill-pack.zip">Skill pack</a>'
        f"</div>"
    )
    body = f"""<div class="report-layout">
<article class="report-body">
{downloads}
{report_fragment(demo)}
</article>
</div>"""
    page = shell(
        "Your engagement · AI Partner",
        "",
        body,
        extra_head='<link rel="stylesheet" href="/report.css">\n',
        scripts='<script src="/report.js" defer></script>\n',
        body_class="report",
    )
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


def _file(state, name):
    mimetype, filename = _FILES[name]
    if name == "report.md":
        return render_report(state), mimetype, filename
    if name == "deck.pptx":
        return build_pptx(state), mimetype, filename
    if name == "kit.zip":
        return build_kit_zip(state), mimetype, filename
    return build_pack_zip(state), mimetype, filename

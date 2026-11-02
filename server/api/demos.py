"""Long-form pages for the three public demo engagements."""
import json
import os
from html import escape

from flask import Blueprint, Response, abort, send_from_directory

from ..demo_schema import valid_demo
from .pages import _shell

bp = Blueprint("demos", __name__)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "demos"))


def load_demo(slug):
    path = os.path.join(ROOT, f"{slug}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not valid_demo(data):
        return None
    return data


@bp.get("/demos")
def index():
    cards = []
    for slug in ("maritime", "keiki", "orchid"):
        demo = load_demo(slug)
        if not demo:
            continue
        cards.append(
            f'<article class="plan"><h2><a href="/demos/{slug}">{escape(demo["company"])}</a></h2><p>{escape(demo["problem"])}</p></article>'
        )
    body = f"""
<p class="kicker">Demos</p>
<h1>Three public engagements.</h1>
<p class="lede">Demo engagement generated from public information. Not commissioned by the company.</p>
<img class="accent" src="/img/brand/character.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="280" height="210">
<div class="plans">{"".join(cards)}</div>
"""
    return Response(_shell("Demos · AI Partner", "/demos", body), mimetype="text/html")


@bp.get("/demos/img/<path:name>")
def demo_img(name):
    return send_from_directory(os.path.join(ROOT, "img"), name)


@bp.get("/demos/<slug>")
def detail(slug):
    demo = load_demo(slug)
    if not demo:
        abort(404)
    return Response(_shell(f"{demo['company']} · AI Partner", "/demos", _report(demo)), mimetype="text/html")


@bp.get("/demos/<slug>/kit.zip")
def kit(slug):
    path = os.path.join(ROOT, f"{slug}.zip")
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(ROOT, f"{slug}.zip", mimetype="application/zip", as_attachment=True, download_name=f"{slug}-kit.zip")


def _report(demo):
    images = _images(demo["slug"])
    gallery = "".join(
        f'<img class="accent" src="/demos/img/{escape(name)}" alt="{escape(demo["company"])} illustration." loading="lazy" width="280" height="210">'
        for name in images
    )
    return f"""
<p class="kicker">Demo · {escape(demo["company"])}</p>
<p class="lede">{escape(demo["disclaimer"])}</p>
<img class="accent" src="/img/brand/character.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="280" height="210">
{gallery}
<h1>{escape(demo["company"])}</h1>
<h2 id="problem">Client problem</h2>
<p>{escape(demo["problem"])}</p>
<h2 id="market">Market analysis</h2>
<p>{escape(demo["market"].get("summary") or "Not generated yet. Run scripts/run_demo.py.")}</p>
<ul>{_citations(demo["market"].get("citations") or [])}</ul>
<h2 id="experts">Expert panel</h2>
{_experts(demo.get("experts") or [])}
<h2 id="debate">Debate</h2>
{_debate(demo.get("debate") or [])}
<h2 id="top5">Top 5</h2>
{_top5(demo.get("top5") or [])}
<h2 id="maturity">Maturity</h2>
{_maturity(demo.get("maturity"))}
<h2 id="chart">Work chart</h2>
{_chart(demo.get("chart"))}
<h2 id="skills">Harness and skill pack</h2>
{_skills(demo.get("skills") or [])}
<p><a href="/demos/{escape(demo["slug"])}/kit.zip">Download the kit zip</a></p>
<h2 id="artifacts">Artifacts</h2>
{_artifacts(demo.get("artifacts") or [])}
"""


def _images(slug):
    folder = os.path.join(ROOT, "img")
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder) if name.startswith(slug + "-") and name.endswith(".webp"))


def _citations(items):
    if not items:
        return "<li>No cited pages yet.</li>"
    return "".join(
        f'<li><a href="{escape(item["url"])}">{escape(item["title"])}</a></li>' for item in items
    )


def _experts(items):
    if not items:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    cards = []
    for item in items:
        cards.append(
            "<article class=\"deliver\"><h3>"
            + escape(item.get("name") or "")
            + "</h3><p class=\"kicker\">"
            + escape(item.get("badge") or "AI-generated expert")
            + " · "
            + escape(item.get("role") or "")
            + "</p><p>"
            + escape(item.get("recommendation") or "")
            + "</p></article>"
        )
    return '<div class="deliver-grid">' + "".join(cards) + "</div>"


def _debate(items):
    if not items:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    return "".join(
        f'<p><strong>Round {escape(str(item.get("round") or ""))} · {escape(item.get("name") or "")}.</strong> {escape(item.get("statement") or "")}</p>'
        for item in items[:12]
    )


def _top5(items):
    if not items:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    blocks = []
    for item in items:
        backers = ", ".join(item.get("backers") or []) or "none listed"
        dissent = "; ".join(
            f"{row.get('name')}: {row.get('why')}" for row in (item.get("dissenters") or [])
        ) or "none listed"
        cite = ""
        if item.get("citation_url"):
            cite = f' <a href="{escape(item["citation_url"])}">Source</a>'
        blocks.append(
            "<article class=\"plan\"><h3>"
            + escape(item.get("title") or "")
            + "</h3><p>"
            + escape(item.get("detail") or "")
            + cite
            + "</p><p>Backers: "
            + escape(backers)
            + "</p><p>Dissent: "
            + escape(dissent)
            + "</p></article>"
        )
    return "".join(blocks)


def _maturity(item):
    if not item:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    return f'<p>Score {escape(str(item.get("score")))}. {escape(item.get("reason") or "")}</p>'


def _chart(chart):
    if not chart:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    rows = []
    for label, key in (("Today", "current"), ("Agent era", "future")):
        for step in chart.get(key) or []:
            rows.append(f'<li>{escape(label)} · {escape(step.get("owner") or "")} · {escape(step.get("step") or "")}</li>')
    return "<ul>" + "".join(rows) + "</ul>"


def _skills(items):
    if not items:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    return "<ul>" + "".join(f"<li>{escape(name)}</li>" for name in items) + "</ul>"


def _artifacts(items):
    if not items:
        return "<p>Not generated yet. Run scripts/run_demo.py.</p>"
    return "<ul>" + "".join(f'<li>{escape(item.get("title") or item.get("id") or "")}</li>' for item in items) + "</ul>"

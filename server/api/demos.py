"""Long-form pages for the three public demo engagements."""
import json
import os
from html import escape

from flask import Blueprint, Response, abort, send_from_directory

from ..demo_schema import valid_demo
from .pages import NAV, _shell

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
    return Response(_page(demo), mimetype="text/html")


@bp.get("/demos/<slug>/kit.zip")
def kit(slug):
    path = os.path.join(ROOT, f"{slug}.zip")
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(ROOT, f"{slug}.zip", mimetype="application/zip", as_attachment=True, download_name=f"{slug}-kit.zip")


_DIVIDER = (
    '<svg class="divider" viewBox="0 0 360 10" aria-hidden="true">'
    '<path d="M0 5 H360" stroke="#d08900" stroke-width="1" stroke-dasharray="2 6"/>'
    '<path d="M4 5 l4 -4 v8 z M20 5 l4 -4 v8 z M36 5 l4 -4 v8 z" fill="#e23d78"/>'
    "</svg>"
)


def _page(demo):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(demo["company"])} · AI Partner</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="stylesheet" href="/app.css">
<link rel="stylesheet" href="/report.css">
</head>
<body class="report">
<div class="bar"><span style="width:100%"></span></div>
<header class="top">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="36" height="36"> AI Partner</a>
  {NAV}
</header>
<div class="report-layout">
<nav class="toc" aria-label="Contents">
  <a href="#summary">Summary</a>
  <a href="#market">Market</a>
  <a href="#experts">Experts</a>
  <a href="#debate">Debate</a>
  <a href="#top5">Top 5</a>
  <a href="#maturity">Maturity</a>
  <a href="#chart">Work chart</a>
  <a href="#skills">Harness</a>
  <a href="#artifacts">Artifacts</a>
</nav>
<article class="report-body">
{_report(demo)}
</article>
</div>
<div class="modal" id="modal" hidden>
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <h2 id="modal-title"></h2>
    <div id="modal-body"></div>
    <button type="button" id="modal-close">Close</button>
  </div>
</div>
<script src="/report.js"></script>
<script src="/voice.js"></script>
</body>
</html>
"""


def _report(demo):
    images = _images(demo["slug"])
    gallery = "".join(
        f'<img class="accent" src="/demos/img/{escape(name)}" alt="{escape(demo["company"])} illustration." loading="lazy" width="280" height="210">'
        for name in images
    )
    cites = demo["market"].get("citations") or []
    top = demo.get("top5") or []
    answer = top[0]["title"] if top else "The public pages below are the record so far."
    maturity = demo.get("maturity") or {}
    score = maturity.get("score") if maturity else None
    return f"""
<p class="kicker">Demo · {escape(demo["company"])}</p>
<p>{escape(demo["disclaimer"])}</p>
<section id="summary">
  <img class="spot" src="/img/brand/character.webp" alt="A multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="96" height="72">
  <h1>{escape(demo["company"])}</h1>
  {_DIVIDER}
  <aside class="note"><strong>The panel's take.</strong> {escape(answer)}</aside>
  <h2>Executive summary</h2>
  <p>{escape(answer)}</p>
  <p>{escape(demo["problem"])}</p>
  <div class="numbers">
    <article><strong>{len(cites)}</strong> cited pages</article>
    <article><strong>{len(demo.get("experts") or [])}</strong> experts</article>
    <article><strong>{escape(str(score) if score else "—")}</strong> maturity</article>
  </div>
  {_top_list(top)}
</section>
<section id="market">
  <img class="spot" src="/img/brand/avatar.webp" alt="" width="72" height="72">
  <h2>Market analysis</h2>
  {_DIVIDER}
  <p>{escape(demo["market"].get("summary") or "Not generated yet. Run scripts/run_demo.py.")}</p>
  <p class="inference">Counts on this page are from the citation list. They are not a market-size estimate.</p>
  <div class="toolbar" id="market-map">{_citation_buttons(cites)}</div>
  <p id="market-tip" class="note" hidden></p>
  {gallery}
</section>
<section id="experts">
  <h2>Expert panel</h2>
  {_DIVIDER}
  <div class="toolbar" id="expert-filters"><button type="button" class="on" data-role="all">All</button></div>
  {_experts(demo.get("experts") or [])}
</section>
<section id="debate">
  <h2>Debate</h2>
  {_DIVIDER}
  <div class="toolbar" id="rounds"></div>
  <div class="timeline" id="timeline">{_debate(demo.get("debate") or [])}</div>
</section>
<section id="top5">
  <h2>Top 5</h2>
  {_DIVIDER}
  <div class="toolbar">
    <button type="button" data-sort="confidence">Confidence</button>
    <button type="button" data-sort="impact">Impact</button>
    <button type="button" data-sort="effort">Effort</button>
    <button type="button" id="toggle-sides">Backers and dissenters</button>
  </div>
  <div class="recs" id="recs">{_top5(top)}</div>
</section>
<section id="maturity">
  <h2>Maturity</h2>
  {_DIVIDER}
  {_maturity(maturity)}
</section>
<section id="chart">
  <h2>Work chart</h2>
  {_DIVIDER}
  <div class="zoom toolbar"><button type="button" id="zoom-in">Zoom in</button><button type="button" id="zoom-out">Zoom out</button></div>
  <div class="diagram" id="diagram">{_chart(demo.get("chart"))}</div>
</section>
<section id="skills">
  <h2>Harness and skill pack</h2>
  {_DIVIDER}
  <div class="toolbar" id="pack-tabs"><button type="button" class="on" data-tab="tree">Files</button><button type="button" data-tab="skills">Skills</button></div>
  <pre class="tree" id="pack-tree">{_tree(demo)}</pre>
  <div id="pack-skills">{_skills(demo.get("skills") or [])}</div>
  <p><a href="/demos/{escape(demo["slug"])}/kit.zip">Download the kit zip</a></p>
</section>
<section id="artifacts">
  <h2>Artifacts</h2>
  {_DIVIDER}
  {_artifacts(demo.get("artifacts") or [])}
</section>
"""


def _images(slug):
    folder = os.path.join(ROOT, "img")
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder) if name.startswith(slug + "-") and name.endswith(".webp"))


def _citation_buttons(items):
    if not items:
        return "<p>No cited pages yet.</p>"
    return "".join(
        f'<button type="button" class="chip" data-url="{escape(item["url"])}" data-note="{escape(item.get("note") or "")}">{escape(item["title"])}</button>'
        for item in items
    )


def _top_list(items):
    if not items:
        return "<p class=\"inference\">Inference: the Top 5 is not in this file yet.</p>"
    return "<ol>" + "".join(f'<li>{escape(item.get("title") or "")}</li>' for item in items) + "</ol>"


def _experts(items):
    if not items:
        return '<p class="inference">Inference: the panel is not in this file yet. Run scripts/run_demo.py.</p>'
    cards = []
    for item in items:
        role = item.get("role") or "General"
        cards.append(
            '<article class="expert" data-role="'
            + escape(role)
            + '"><h3><button type="button">'
            + escape(item.get("name") or "")
            + "</button></h3><p class=\"kicker\">"
            + escape(item.get("badge") or "AI-generated expert")
            + " · "
            + escape(role)
            + '</p><p class="more">'
            + escape(item.get("recommendation") or "")
            + "</p></article>"
        )
    return '<div class="experts" id="expert-list">' + "".join(cards) + "</div>"


def _debate(items):
    if not items:
        return '<p class="inference">Inference: the debate is not in this file yet.</p>'
    return "".join(
        f'<p data-round="{escape(str(item.get("round") or ""))}"><strong>Round {escape(str(item.get("round") or ""))} · {escape(item.get("name") or "")}.</strong> {escape(item.get("statement") or "")}</p>'
        for item in items
    )


def _top5(items):
    if not items:
        return '<p class="inference">Inference: the Top 5 is not in this file yet.</p>'
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
            '<article class="rec" data-confidence="'
            + escape(str(item.get("confidence") or ""))
            + '" data-impact="'
            + escape(str(item.get("impact") or ""))
            + '" data-effort="'
            + escape(str(item.get("effort") or ""))
            + '"><h3>'
            + escape(item.get("title") or "")
            + "</h3><p>"
            + escape(item.get("detail") or "")
            + cite
            + '</p><p class="sides">Backers: '
            + escape(backers)
            + "</p><p class=\"sides\">Dissent: "
            + escape(dissent)
            + "</p></article>"
        )
    return "".join(blocks)


def _maturity(item):
    if not item:
        return '<p class="inference">Inference: a maturity score is not in this file yet.</p><div class="bars" id="maturity-bars"></div>'
    score = int(item.get("score") or 0)
    labels = {1: "Invoice-led", 2: "Pilot-led", 3: "Hybrid", 4: "Machine-led"}
    rows = []
    for value, label in labels.items():
        width = 100 if value <= score else 12
        rows.append(
            f'<div class="barline"><span>{escape(label)}</span><span class="meter" title="{escape(item.get("reason") or label)}"><i style="width:{width}%"></i></span></div>'
        )
    return f'<p>Score {score}. {escape(item.get("reason") or "")}</p><div class="bars" id="maturity-bars">{"".join(rows)}</div>'


def _chart(chart):
    if not chart:
        return '<p class="inference">Inference: the work chart is not in this file yet.</p>'
    rows = []
    for label, key in (("Today", "current"), ("Agent era", "future")):
        for step in chart.get(key) or []:
            rows.append(
                f'<p><strong>{escape(label)}</strong> · {escape(step.get("owner") or "")} · {escape(step.get("step") or "")}. {escape(step.get("task") or "")}</p>'
            )
    return "".join(rows)


def _tree(demo):
    lines = ["kit/", "  problem.md", "  market.md", "  top5.json", "  skills/"]
    for name in demo.get("skills") or []:
        lines.append("    " + name)
    lines.append("  artifacts/")
    for item in demo.get("artifacts") or []:
        lines.append("    " + str(item.get("id") or "note") + ".html")
    return escape("\n".join(lines))


def _skills(items):
    if not items:
        return '<p class="inference">Inference: the skill pack is not in this file yet.</p>'
    return "<ul>" + "".join(f"<li>{escape(name)}</li>" for name in items) + "</ul>"


def _artifacts(items):
    if not items:
        return '<p class="inference">Inference: artifact files are not in this engagement yet.</p>'
    buttons = []
    for item in items:
        title = item.get("title") or item.get("id") or "Artifact"
        body = item.get("body") or title
        buttons.append(
            f'<button type="button" class="artifact" data-title="{escape(title)}" data-body="{escape(body)}">{escape(title)}</button>'
        )
    return '<div class="toolbar">' + "".join(buttons) + "</div>"

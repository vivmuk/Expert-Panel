"""Long-form pages for the three public demo engagements."""
import json
import os
import re
import zlib
from html import escape

from flask import Blueprint, Response, abort, send_from_directory

from .. import art
from ..catalog import by_id
from ..demo_schema import DISCLAIMER, valid_demo
from ..icons import icon
from ..live_report import step_name, swimlane
from .pages import (
    ARTIFACT_ICONS,
    DECK_EMBED_SCRIPT,
    deck_embed,
    page_head,
    shell,
    task_slug,
)

bp = Blueprint("demos", __name__)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "demos"))
SLUGS = ("maritime", "keiki", "orchid")


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
    for slug in SLUGS:
        demo = load_demo(slug)
        if not demo:
            continue
        stats = [
            f'{len(demo.get("experts") or [])} experts',
            f'{len(demo.get("debate") or [])} debate turns',
            f'Top {len(demo.get("top5") or [])}',
            f'{len(_kit_paths(demo))} kit files',
        ]
        if _has_deck(slug):
            stats.append("Client deck")
        pills = "".join(f'<span class="pill">{escape(s)}</span>' for s in stats)
        cover = f"demos/img/{slug}-cover.webp"
        image = art.img(cover, eager=True) if art.exists(cover) else ""
        cards.append(
            f"""<a class="demo-card gb spot reveal" href="/demos/{slug}">
  {image}
  <div class="demo-copy">
    <p class="kicker">{escape(_site(demo))}</p>
    <h2>{escape(demo["company"])}{icon("arrow-right")}</h2>
    <p>{escape(_client_problem(demo))}</p>
    <div class="demo-stats">{pills}</div>
  </div>
</a>"""
        )
    body = page_head(
        "Demos",
        "Three public engagements, <em>run end to end by agents</em>.",
        "Each one starts from a company's public pages. AI Partner agents research it, 20 AI experts debate it over two rounds, a judge ranks the Top 5, and the harness kit ships with the report.",
        f'<p class="disclaimer">{icon("info")}<span>{escape(DISCLAIMER)}</span></p>',
    ) + f"""
<div class="demo-grid">{"".join(cards)}</div>
<section class="cta-band gb spot reveal">
  <div><p class="kicker">Your first engagement is free</p><h2>Run the same engagement on your own problem.</h2></div>
  <a class="btn primary" href="/chat">{icon("message-circle")}Start in chat</a>
</section>
"""
    return Response(shell("Demos · AI Partner", "/demos", body), mimetype="text/html")


@bp.get("/demos/img/<path:name>")
def demo_img(name):
    return send_from_directory(os.path.join(ROOT, "img"), name)


@bp.get("/demos/<slug>")
def detail(slug):
    demo = load_demo(slug)
    if not demo:
        abort(404)
    return Response(_page(demo), mimetype="text/html")


@bp.get("/demos/<slug>/kit/<path:name>")
def kit_file(slug, name):
    if slug not in SLUGS:
        abort(404)
    base = os.path.join(ROOT, slug, "kit")
    if not os.path.isfile(os.path.join(base, name)):
        abort(404)
    kind = "application/json; charset=utf-8" if name.endswith(".json") else "text/markdown"
    return send_from_directory(base, name, mimetype=kind)


@bp.get("/demos/<slug>/deck")
@bp.get("/demos/<slug>/deck/")
def client_deck(slug):
    if slug not in SLUGS or not os.path.isfile(os.path.join(ROOT, slug, "deck.html")):
        abort(404)
    return send_from_directory(os.path.join(ROOT, slug), "deck.html", mimetype="text/html")


@bp.get("/demos/<slug>/kit.zip")
def kit(slug):
    path = os.path.join(ROOT, f"{slug}.zip")
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(ROOT, f"{slug}.zip", mimetype="application/zip", as_attachment=True, download_name=f"{slug}-kit.zip")


TOC = (
    ("summary", "Summary"),
    ("market", "Market"),
    ("experts", "Experts"),
    ("debate", "Debate"),
    ("synthesis", "Synthesis"),
    ("top5", "Top 5"),
    ("maturity", "Maturity"),
    ("chart", "Work chart"),
    ("skills", "Harness kit"),
    ("artifacts", "Artifacts"),
)


def _page(demo):
    links = "".join(
        f'<a href="#{key}"><span>{n:02d}</span>{label}</a>' for n, (key, label) in enumerate(TOC, 1)
    )
    body = f"""<div class="report-layout">
<nav class="toc" aria-label="On this page"><p class="kicker">On this page</p>{links}</nav>
<article class="report-body">
{_report(demo)}
</article>
</div>"""
    return shell(
        f'{demo["company"]} · AI Partner',
        "/demos",
        body,
        extra_head='<link rel="stylesheet" href="/report.css">\n',
        scripts='<script src="/report.js" defer></script>\n' + (DECK_EMBED_SCRIPT if _has_deck(demo["slug"]) else ""),
        body_class="report",
    )


def report_fragment(demo):
    return _report(demo)


def _report(demo):
    live = demo.get("live")
    cites = demo["market"].get("citations") or []
    top = demo.get("top5") or []
    experts = demo.get("experts") or []
    debate = demo.get("debate") or []
    maturity = demo.get("maturity") or {}
    synthesis = demo.get("synthesis") or {}
    score = maturity.get("score") if maturity else None
    take = synthesis.get("cohesive_summary") or (top[0]["title"] if top else "The public pages below are the record so far.")
    stats = (
        (len(cites), "cited pages"),
        (len(experts), "AI experts"),
        (len(debate), "debate turns"),
        (len(top), "top moves"),
        (f"{score}/4" if score else "—", "AI maturity"),
        (len(_kit_paths(demo)), "kit files"),
    )
    stat_html = "".join(f'<div class="stat"><strong>{escape(str(v))}</strong><span>{escape(k)}</span></div>' for v, k in stats)
    frame = demo.get("frame") if live else None
    plan = demo.get("plan") if live else None
    summary = f"""
<section id="summary" class="report-section">
  <div class="report-hero">
    {_art(demo, "cover", eager=True)}
    <div class="report-hero-copy">
      {_hero_kicker(demo)}
      <h1>{escape(demo["company"])}</h1>
      <p class="lede">{escape(_client_problem(demo))}</p>
      {"" if live else f'<p class="disclaimer">{icon("info")}<span>{escape(DISCLAIMER)}</span></p>'}
      <div class="hero-actions">{_hero_actions(demo)}</div>
    </div>
  </div>
  <div class="stats report-stats">{stat_html}</div>
  <div class="exec card">
    <p class="kicker">{icon("sparkles")}Executive summary</p>
    <h2 class="sr-only">Executive summary</h2>
    {f'<p class="question">{escape(frame["key_question"])}</p>' if frame else ""}
    <p class="take">{escape(take)}</p>
    {_top_list(top)}
    {_decisions(plan)}
  </div>
  {_deck_embed(demo)}
</section>"""
    sections = [summary]
    counter = {"n": 1}

    def add(key, title, lede, inner):
        counter["n"] += 1
        number = "%02d" % counter["n"]
        head = _section_head(number, title, lede)
        sections.append(f'\n<section id="{key}" class="report-section">\n  {head}\n  {inner}\n</section>')

    if frame:
        add("question", "The question", "The situation, the complication, and the one question this engagement answers. Then the options the panel weighed.", _frame(frame))
    add("market", "Research" if live else "Market analysis", f"{len(cites)} public pages, each with the note the research agents kept.", _art(demo, "market") + f'\n  <p class="prose">{escape(demo["market"].get("summary") or "Not generated yet. Run scripts/run_demo.py.")}</p>\n  {_citations(cites)}')
    add("experts", "Expert panel", f"{len(experts)} AI-generated experts, each with a distinct lens. Open a card for the full analysis.", _experts(experts))
    add("debate", "Debate", "Two rounds. Each expert answers a named colleague.", _art(demo, "panel") + "\n  " + _debate(debate))
    add("synthesis", "Judge and synthesis" if live else "Synthesis", "Where the panel converged, and what it may be missing.", _synthesis(synthesis))
    add("top5", "Top 5", "Ranked by the judge after the debate. Sort them to see the trade-offs.", _top5(top))
    if frame:
        add("value", "Value at stake", "Where the money or time comes from, how to size it, and what must be true.", _value_section(frame))
    if plan:
        add("risks", "Risk register", "Each risk with its likelihood, impact, mitigation, and the owner who watches it.", _risks(plan))
    add("maturity", "Maturity", "Where the team sits on the AI maturity ladder today.", _maturity(maturity))
    add("chart", "Work chart", "Every step today, and who owns it in the agent era.", _chart(demo.get("chart")))
    if plan:
        add("plan", "First 90 days", "Milestones with owners and decision gates, the measures that show it is working, and who needs to be aligned.", _plan(plan))
    add("skills", "Harness and skill pack", "The files your team keeps running after the engagement. Every file is AI-generated.", _art(demo, "build") + "\n  " + _kit(demo))
    add("artifacts", "Deliverables" if live else "Artifacts", "The client deck, memo, work chart, brief, and roadmap from this engagement. Open any of them here, as a full page, or as a file." if live else "The catalog artifacts this engagement feeds. Generate any of them for your own problem in chat.", _deliverables(demo) if live else _artifacts(demo.get("artifacts") or []))
    if live and demo.get("method"):
        add("method", "How this engagement was run", "The method, the sources, and the limits of what this report can claim.", _ul(demo["method"], "dots-list method-list"))
    return "".join(sections) + "\n"


def _sentence(text):
    """End a fragment with one full stop, never two."""
    text = " ".join(str(text or "").split())
    return text if not text or text[-1] in ".!?" else text + "."


def _decisions(plan):
    if not plan or not plan.get("decisions"):
        return ""
    rows = "".join(
        f'<li><a href="#plan"><span class="n">{n}</span><span>{escape(_sentence(d["decision"]))}{escape(" Owner: " + _sentence(d["owner"])) if d.get("owner") else ""}{escape(" By " + _sentence(d["by_when"])) if d.get("by_when") else ""}</span></a></li>'
        for n, d in enumerate(plan["decisions"], 1)
    )
    return f'<p class="kicker decisions-kicker">{icon("list-checks")}Decisions required</p><ol class="top-list decisions">{rows}</ol>'


_VERDICT_PILL = {"recommended": "cobalt", "conditional": "amber", "rejected": "ink"}


def _frame(frame):
    scq = "".join(
        f'<div class="card"><h3>{icon(glyph)}{label}</h3><p>{escape(text)}</p></div>'
        for glyph, label, text in (("map", "Situation", frame.get("situation")), ("triangle-alert", "Complication", frame.get("complication")), ("crosshair", "Question", frame.get("key_question")))
        if text
    )
    options = "".join(
        f'<li><span class="pill {_VERDICT_PILL.get(o.get("verdict"), "")}">{escape(o.get("verdict") or "")}</span><b>{escape(o.get("name") or "")}. {escape(o.get("summary") or "")}</b>'
        f'<span>{escape(_sentence(o.get("why")))}{escape(" Upside: " + _sentence(o["upside"])) if o.get("upside") else ""}{escape(" Downside: " + _sentence(o["downside"])) if o.get("downside") else ""}</span></li>'
        for o in frame.get("options") or []
    )
    return f'<div class="synth-grid three">{scq}</div><div class="card next-steps"><h3>{icon("git-fork")}Options considered</h3><ol class="next-list">{options}</ol></div>'


def _value_section(frame):
    drivers = "".join(
        f'<div class="card"><h3>{icon("badge-dollar-sign")}{escape(v.get("driver") or "")}</h3><p>{escape(v.get("mechanism") or "")}</p>'
        + (f'<p class="how"><b>How to size it.</b> {escape(v["how_to_size"])}</p>' if v.get("how_to_size") else "")
        + "</div>"
        for v in frame.get("value_drivers") or []
    )
    must = _ul(frame.get("assumptions"), "dots-list")
    open_rows = "".join(
        f'<li><span class="pill">Open</span><b>{escape(q.get("question") or "")}</b><span>{escape(q.get("how_to_answer") or "")}</span></li>'
        for q in frame.get("open_questions") or []
    )
    return f"""<div class="synth-grid">{drivers}</div>
{_empty("Figures that are not in the cited sources are assumptions for the client's finance team to size.")}
<div class="synth-grid">
  <div class="card"><h3>{icon("clipboard-check")}What must be true</h3>{must or _empty("No assumptions were recorded.")}</div>
  <div class="card next-steps"><h3>{icon("file-search")}Open questions</h3><ol class="next-list">{open_rows}</ol></div>
</div>"""


def _risks(plan):
    rows = "".join(
        f'<tr><td><b>{escape(r.get("risk") or "")}</b></td><td>{_level("", r.get("likelihood"))}</td><td>{_level("", r.get("impact"))}</td><td>{escape(r.get("mitigation") or "")}</td><td>{escape(r.get("owner") or "-")}</td></tr>'
        for r in plan.get("risks") or []
    )
    return f'<div class="table-wrap"><table class="report-table risks"><thead><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th><th>Owner</th></tr></thead><tbody>{rows}</tbody></table></div>'


def _plan(plan):
    from ..chatjob import WINDOWS

    windows = "".join(
        f'<div class="card"><h3>{icon("milestone")}{escape(window)}</h3><ul class="dots-list">'
        + "".join(
            f'<li><b>{escape(m.get("milestone") or "")}</b>{escape(" (" + m["owner"] + ")") if m.get("owner") else ""}{escape(" Gate: " + m["gate"]) if m.get("gate") else ""}</li>'
            for m in plan.get("milestones") or [] if m.get("window") == window
        )
        + "</ul></div>"
        for window in WINDOWS
    )
    kpis = "".join(
        f'<tr><td><b>{escape(k.get("metric") or "")}</b></td><td>{escape(k.get("direction") or "")}</td><td>{escape(k.get("cadence") or "-")}</td><td>{escape(k.get("why") or "")}</td></tr>'
        for k in plan.get("kpis") or []
    )
    people = "".join(
        f'<tr><td><b>{escape(p.get("who") or "")}</b></td><td><span class="pill">{escape(p.get("role") or "")}</span></td><td>{escape(p.get("needs") or "")}</td></tr>'
        for p in plan.get("stakeholders") or []
    )
    cadence = f'<p class="prose"><strong>Cadence.</strong> {escape(plan["cadence"])}</p>' if plan.get("cadence") else ""
    return f"""<div class="synth-grid three">{windows}</div>
{cadence}
<h3 class="sub-head">How we will know it is working</h3>
<div class="table-wrap"><table class="report-table kpis"><thead><tr><th>Measure</th><th>Direction</th><th>Cadence</th><th>Why</th></tr></thead><tbody>{kpis}</tbody></table></div>
{f'<h3 class="sub-head">Who needs to be aligned</h3><div class="table-wrap"><table class="report-table people"><thead><tr><th>Who</th><th>Role</th><th>What they need</th></tr></thead><tbody>{people}</tbody></table></div>' if people else ""}"""


def _has_deck(slug):
    return os.path.isfile(os.path.join(ROOT, slug, "deck.html"))


def _deck_button(slug):
    if not _has_deck(slug):
        return ""
    return f'<a class="btn primary deck-btn" href="/demos/{escape(slug)}/deck" target="_blank" rel="noopener">{icon("monitor-play")}Open the client deck</a>'


def _slide_count(slug):
    with open(os.path.join(ROOT, slug, "deck.html"), encoding="utf-8") as handle:
        return len(re.findall(r'<section class="slide\b', handle.read()))


def _hero_kicker(demo):
    if demo.get("live"):
        return f'<p class="kicker">{icon("sparkles")}Live engagement<span aria-hidden="true">/</span>{len(demo.get("experts") or [])} AI experts</p>'
    return f'<p class="kicker"><a href="/demos">Demos</a><span aria-hidden="true">/</span>{escape(_site(demo))}</p>'


def _hero_actions(demo):
    if demo.get("live"):
        return (
            f'<button type="button" class="btn primary deck-btn" data-artifact="deck">{icon("monitor-play")}Open the client deck</button>'
            f'<button type="button" class="btn ghost" data-download="pptx">{icon("download")}Download .pptx</button>'
            f'<a class="btn ghost" href="#top5">{icon("trophy")}Jump to the Top 5</a>'
            f'<button type="button" class="btn ghost" data-download="kit">{icon("package")}Harness kit</button>'
        )
    slug = escape(demo["slug"])
    return (
        f'{_deck_button(demo["slug"])}<a class="btn ghost" href="#top5">{icon("trophy")}Jump to the Top 5</a>'
        f'<a class="btn ghost" href="/demos/{slug}/kit.zip" download>{icon("download")}Kit zip</a>'
    )


def _deck_embed(demo):
    slug = demo["slug"]
    if demo.get("live") or not _has_deck(slug):
        return ""
    return deck_embed(
        f"/demos/{slug}/deck",
        f'{demo["company"]} client deck · AI Partner',
        "The client deck",
        kicker=f'{demo["company"]} · {_slide_count(slug)} slides',
        lede="The whole engagement as the deck your team would present.",
    )


def _section_head(number, title, lede):
    return f'<header class="section-head"><p class="kicker"><b>{number}</b></p><h2>{escape(title)}</h2><p class="muted">{escape(lede)}</p></header>'


def _art(demo, kind, eager=False):
    path = (demo.get("art") or {}).get(kind) or f"demos/img/{demo['slug']}-{kind}.webp"
    if not art.exists(path):
        return ""
    cls = "hero-art" if kind == "cover" else "section-art"
    return art.img(path, cls, eager=eager)


def _site(demo):
    first = (demo.get("problem") or "").split("\n", 1)[0]
    if "(" in first and ")" in first:
        return first.split("(", 1)[1].split(")", 1)[0]
    return demo["company"]


def _client_problem(demo):
    text = demo.get("problem") or ""
    marker = "The client problem:"
    if marker in text:
        part = text.split(marker, 1)[1].split("\n\n", 1)[0].strip()
        return part[:1].upper() + part[1:]
    return text.split("\n\n", 1)[0]


def _kit_paths(demo):
    return ((demo.get("kit_files") or {}).get("paths")) or []


def _initials(name):
    words = [w for w in (name or "").replace(".", " ").split() if w.lower() not in ("dr", "prof", "mr", "ms", "mrs")]
    if not words:
        return "AI"
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def _hue(name):
    return 200 + zlib.crc32((name or "").encode()) % 140


def _avatar(name):
    return f'<span class="initials" style="--h:{_hue(name)}" aria-hidden="true">{escape(_initials(name))}</span>'


def _value(raw):
    return str(raw or "").strip().lower()


def _level(label, raw, cls=""):
    value = _value(raw)
    shown = value.capitalize() if value else "—"
    return (
        f'<span class="level {cls}" data-v="{escape(value)}"><span>{label}</span>'
        f'<span class="bars" aria-hidden="true"><i></i><i></i><i></i></span><b>{escape(shown)}</b></span>'
    )


def _ul(items, cls=""):
    items = [x for x in (items or []) if x]
    if not items:
        return ""
    klass = f' class="{cls}"' if cls else ""
    return f"<ul{klass}>" + "".join(f"<li>{escape(str(x))}</li>" for x in items) + "</ul>"


def _empty(text):
    return f'<p class="inference">{icon("info")}<span>{escape(text)}</span></p>'


def _top_list(items):
    if not items:
        return _empty("The Top 5 is not in this file yet.")
    rows = "".join(
        f'<li><a href="#rec-{n}"><span class="n">{n}</span><span>{escape(item.get("title") or "")}</span></a></li>'
        for n, item in enumerate(items, 1)
    )
    return f'<ol class="top-list">{rows}</ol>'


def _citations(items):
    if not items:
        return _empty("No cited pages yet.")
    rows = []
    for item in items:
        url = item.get("url") or ""
        host = url.split("//", 1)[-1].split("/", 1)[0]
        note = f'<span>{escape(item["note"])}</span>' if item.get("note") else ""
        rows.append(
            f'<li><a href="{escape(url)}" target="_blank" rel="noopener"><small>{escape(host)}</small>'
            f'<b>{escape(item.get("title") or url)}</b>{note}</a></li>'
        )
    return f'<ul class="sources cite-list">{"".join(rows)}</ul>'


def _experts(items):
    if not items:
        return _empty("The panel is not in this file yet. Run scripts/run_demo.py.")
    cards = []
    for item in items:
        name = item.get("name") or ""
        role = item.get("role") or "General"
        blob = " ".join([name, role, item.get("lens") or "", item.get("background") or ""]).lower()
        cards.append(
            f"""<article class="expert-card" data-expert="{escape(blob)}">
  <header>{_avatar(name)}<div><b>{escape(name)}</b><small>{escape(role)}</small></div></header>
  <p class="lens">{escape(item.get("lens") or "")}</p>
  <p class="rec-line"><span class="pill cobalt">Recommends</span> {escape(item.get("recommendation") or "")}</p>
  {_expert_detail(item)}
</article>"""
        )
    return f"""<div class="report-tools">
  <div class="search gb small-search">{icon("search")}<label class="sr-only" for="expert-q">Search experts</label><input id="expert-q" type="search" placeholder="Search {len(items)} experts by name, role, or lens" autocomplete="off"></div>
  <p class="search-count" id="expert-count" role="status">{len(items)} experts</p>
  <button type="button" class="btn small ghost expand-all" data-expand="expert-list" aria-pressed="false">{icon("chevrons-up-down")}<span>Expand all</span></button>
</div>
<div class="expert-grid report-experts" id="expert-list">{"".join(cards)}</div>
{_empty_filter("expert-empty", "No expert matches that search.")}"""


def _empty_filter(element_id, text):
    return f'<p class="inference" id="{element_id}" hidden>{icon("search")}<span>{escape(text)}</span></p>'


def _expert_detail(item):
    parts = []
    if item.get("insight"):
        parts.append(f"<p><strong>Insight.</strong> {escape(item['insight'])}</p>")
    if item.get("background"):
        parts.append(f"<p><strong>Background.</strong> {escape(item['background'])}</p>")
    if item.get("risks"):
        parts.append(f"<p><strong>Risks.</strong> {escape(item['risks'])}</p>")
    if item.get("opportunities"):
        parts.append(f"<p><strong>Opportunities.</strong> {escape(item['opportunities'])}</p>")
    for row in item.get("insights") or []:
        confidence = _value(row.get("confidence_level"))
        parts.append(
            f'<div class="insight"><h4>{escape(row.get("insight") or "")}</h4>'
            + (f'<span class="pill">{escape(confidence)} confidence</span>' if confidence else "")
            + f"<p>{escape(row.get('supporting_reasoning') or '')}</p>"
            + ("<p><strong>How to do it</strong></p>" + _ul(row.get("implementation_ideas")) if row.get("implementation_ideas") else "")
            + ("<p><strong>Risks</strong></p>" + _ul(row.get("identified_risks")) if row.get("identified_risks") else "")
            + ("<p><strong>Opportunities</strong></p>" + _ul(row.get("identified_opportunities")) if row.get("identified_opportunities") else "")
            + "</div>"
        )
    if item.get("said"):
        rows = "".join(
            f'<li><span class="pill">Round {escape(str(row.get("round") or ""))}</span>'
            + (f'<b>to {escape(row["responding_to"])}</b> ' if row.get("responding_to") else "")
            + f'{escape(row.get("statement") or "")}</li>'
            for row in item["said"]
        )
        parts.append(f'<p><strong>In the debate</strong></p><ul class="said">{rows}</ul>')
    if not parts:
        return ""
    return f'<details class="more"><summary>Full analysis{icon("chevron-down")}</summary><div class="detail">{"".join(parts)}</div></details>'


def _debate(items):
    if not items:
        return _empty("The debate is not in this file yet.")
    rounds = sorted({str(item.get("round") or "") for item in items if item.get("round")})
    tabs = '<button type="button" class="chip on" data-round-tab="all" aria-pressed="true">All rounds</button>' + "".join(
        f'<button type="button" class="chip" data-round-tab="{escape(r)}" aria-pressed="false">Round {escape(r)} <span>{sum(1 for i in items if str(i.get("round")) == r)}</span></button>'
        for r in rounds
    )
    rows = []
    for item in items:
        name = item.get("name") or ""
        reply = item.get("responding_to")
        to = f'<span class="to">replying to {escape(reply)}</span>' if reply else ""
        rnd = escape(str(item.get("round") or ""))
        rows.append(
            f"""<li data-round="{rnd}">{_avatar(name)}<div>
  <p class="who"><b>{escape(name)}</b>{to}<span class="pill">Round {rnd}</span></p>
  <p class="statement">{escape(item.get("statement") or "")}</p>
  <button type="button" class="linkish read-more" hidden>Read all</button>
</div></li>"""
        )
    return f'<div class="chips round-tabs" role="group" aria-label="Debate rounds">{tabs}</div><ol class="debate-list report-debate" id="timeline">{"".join(rows)}</ol>'


def _synthesis(item):
    if not item:
        return _empty("The synthesis is not in this file yet.")
    steps = "".join(
        f'<li><span class="pill {"magenta" if _value(s.get("priority")) in ("high", "now") else "cobalt"}">{escape(s.get("priority") or "")}</span>'
        f'<b>{escape(s.get("step_description") or "")}</b><span>{escape(s.get("suggested_rationale") or "")}</span></li>'
        for s in item.get("actionable_next_steps") or []
    )
    judges = "".join(
        f'<article class="judge card"><header>{_avatar(p.get("name"))}<div><b>{escape(p.get("name") or "")}</b><small>{escape(p.get("title") or "")}</small></div></header>'
        f'<p>{escape(p.get("insight") or "")}</p><p class="rec-line"><span class="pill cobalt">Asks for</span> {escape(p.get("recommendation") or "")}</p></article>'
        for p in item.get("judges") or []
    )
    judges = f'<h3 class="sub-head">The judge\'s panel</h3><div class="judge-grid">{judges}</div>' if judges else ""
    red = item.get("red_team") or {}
    attacks = "".join(
        f'<li><b>{escape(a.get("threat") or "")}</b><span>{escape(a.get("why") or "")}</span><span class="fix">{icon("shield-check")}{escape(a.get("mitigation") or "")}</span></li>'
        for a in red.get("attacks") or []
    )
    red_html = f'<div class="card red-team"><h3>{icon("swords")}Red team</h3><p class="take">{escape(red.get("top_risk") or "")}</p><ul class="attack-list">{attacks}</ul></div>' if attacks else ""
    return f"""<p class="take prose">{escape(item.get("cohesive_summary") or "")}</p>
<div class="synth-grid">
  <div class="card"><h3>{icon("sparkles")}Key themes</h3>{_ul(item.get("key_themes"), "dots-list")}</div>
  <div class="card"><h3>{icon("eye-off")}Blind spots</h3>{_ul(item.get("potential_blind_spots"), "dots-list")}</div>
</div>
<div class="card next-steps"><h3>{icon("list-checks")}Next steps</h3><ol class="next-list">{steps}</ol></div>
{judges}{red_html}"""


def _top5(items):
    if not items:
        return _empty("The Top 5 is not in this file yet.")
    blocks = []
    for rank, item in enumerate(items, 1):
        backers = item.get("backers") or []
        chips = "".join(f'<span class="pill">{escape(b)}</span>' for b in backers)
        dissent = "".join(
            f"<li><b>{escape(row.get('name') or '')}</b> {escape(row.get('why') or '')}</li>" for row in (item.get("dissenters") or [])
        )
        cite = ""
        if item.get("citation_url"):
            cite = f'<a class="cite" href="{escape(item["citation_url"])}" target="_blank" rel="noopener">{icon("link")}Source</a>'
        extra = ""
        if item.get("rationale"):
            extra += f"<p><strong>Why.</strong> {escape(item['rationale'])}</p>"
        for label, key in (("Risks", "risks"), ("Metrics to track", "metrics"), ("Next steps", "next_steps")):
            if item.get(key):
                extra += f"<p><strong>{label}</strong></p>" + _ul(item[key])
        if dissent:
            extra += f'<p><strong>Dissent</strong></p><ul class="dissent">{dissent}</ul>'
        more = f'<details class="more"><summary>Why, risks, metrics, next steps{icon("chevron-down")}</summary><div class="detail">{extra}</div></details>' if extra else ""
        blocks.append(
            f"""<li class="rec card" id="rec-{rank}" data-rank="{rank}" data-confidence="{escape(_value(item.get("confidence")))}" data-impact="{escape(_value(item.get("impact")))}" data-effort="{escape(_value(item.get("effort")))}">
  <span class="rank">{rank}</span>
  <div>
    <h3>{escape(item.get("title") or "")}</h3>
    <p>{escape(item.get("detail") or "")}</p>
    <div class="levels">{_level("Confidence", item.get("confidence"))}{_level("Impact", item.get("impact"))}{_level("Effort", item.get("effort"), "effort")}{cite}</div>
    {f'<div class="backers"><span>Backed by {len(backers)}</span>{chips}</div>' if backers else ""}
    {more}
  </div>
</li>"""
        )
    sorts = "".join(
        f'<button type="button" class="chip{" on" if key == "rank" else ""}" data-sort="{key}" aria-pressed="{"true" if key == "rank" else "false"}">{label}</button>'
        for key, label in (("rank", "Judge's rank"), ("confidence", "Confidence"), ("impact", "Impact"), ("effort", "Lowest effort"))
    )
    return f'<div class="chips sort-bar" role="group" aria-label="Sort the Top 5"><span class="kicker">Sort</span>{sorts}</div><ol class="top5 report-top5" id="recs">{"".join(blocks)}</ol>'


LADDER = (
    (1, "Invoice-led", "Outside work is bought by the invoice."),
    (2, "Pilot-led", "Agents run in pilots beside the team."),
    (3, "Hybrid", "Agents and people split the steps."),
    (4, "Machine-led", "Agents run the steps; people decide."),
)


def _maturity(item):
    if not item:
        return _empty("A maturity score is not in this file yet.")
    score = int(item.get("score") or 0)
    rungs = "".join(
        f'<li class="{"on" if value == score else ("past" if value < score else "")}"{" aria-current=step" if value == score else ""}>'
        f'<span class="n">{value}</span><b>{escape(label)}</b><span>{escape(text)}</span></li>'
        for value, label, text in LADDER
    )
    return f'<ol class="ladder">{rungs}</ol><p class="prose"><strong>Score {score} of 4.</strong> {escape(item.get("reason") or "")}</p>'


def _owner(raw):
    value = _value(raw)
    cls = "agent" if "agent" in value else ("hybrid" if "hybrid" in value else "human")
    return f'<span class="own {cls}">{escape(raw or "Human")}</span>'


def _steps(rows):
    return "".join(
        f'<li>{_owner(step.get("owner"))}<b>{escape(step_name(step) or step.get("task") or "")}</b>'
        f'<span class="task">{escape(step.get("task") if step_name(step) else "")}</span></li>'
        for step in rows
    )


def _chart(chart):
    if not chart:
        return _empty("The work chart is not in this file yet.")
    future = chart.get("future") or []
    counts = {}
    for step in future:
        counts[step.get("owner") or "Human"] = counts.get(step.get("owner") or "Human", 0) + 1
    tally = "".join(
        f'<div class="tally-box {o.split()[-1].lower()}"><b>{counts.get(o, 0)}</b><span>{o}</span></div>' for o in ("Human", "Hybrid", "AI Agent")
    )
    return f"""<p class="prose">{escape(chart.get("summary") or "")}</p>
<div class="tally">{tally}</div>
<div class="report-chart">
  <h3 class="sub-head">Agent era</h3>
  {swimlane({"future": [s for s in future if s.get("owner") in ("Human", "Hybrid", "AI Agent")]})}
  <h3 class="sub-head">Today</h3>
  <ol class="steps-list">{_steps(chart.get("current") or [])}</ol>
</div>"""


def _kit(demo):
    slug = escape(demo["slug"])
    paths = _kit_paths(demo)
    if demo.get("live"):
        files = "".join(f'<li><span class="file">{icon("file-text")}<span>{escape(p)}</span></span></li>' for p in paths)
    else:
        files = "".join(
            f'<li><a href="/demos/{slug}/{escape(p)}" target="_blank" rel="noopener">{icon("file-text")}<span>{escape(p[4:])}</span></a></li>'
            for p in paths
        )
    described = {s.get("name"): s.get("description") for s in ((demo.get("kit_files") or {}).get("skills") or []) if isinstance(s, dict)}
    skills = "".join(
        f'<article class="skill card">{icon("puzzle")}<h3>{escape(name)}</h3><p>{escape(described.get(name) or "")}</p></article>'
        for name in demo.get("skills") or []
    )
    out = ""
    if skills:
        out += f'<div class="skill-grid">{skills}</div>'
    else:
        out += _empty("The skill pack is not in this file yet.")
    if files:
        out += f'<h3 class="sub-head">Kit files</h3><ul class="kit-files">{files}</ul>'
    if demo.get("live"):
        return out + (
            f'<div class="hero-actions"><button type="button" class="btn primary" data-download="kit">{icon("package")}Download the harness kit</button>'
            f'<button type="button" class="btn ghost" data-download="skill-pack">{icon("puzzle")}Skill pack zip</button>'
            f'<button type="button" class="btn ghost" data-download="report">{icon("file-text")}Report .md</button>'
            f'<a class="btn ghost" href="/connect">{icon("plug")}Run it in your own agent</a></div>'
        )
    out += f'<div class="hero-actions"><a class="btn primary" href="/demos/{slug}/kit.zip" download>{icon("download")}Download the kit zip</a>{_deck_button(demo["slug"]).replace("btn primary", "btn ghost")}<a class="btn ghost" href="/connect">{icon("plug")}Run it in your own agent</a></div>'
    return out


def _artifacts(items):
    if not items:
        return _empty("Artifact files are not in this engagement yet.")
    cards = []
    for item in items:
        entry = by_id(item.get("id")) or {}
        title = entry.get("title") or item.get("title") or item.get("id") or "Artifact"
        purpose = entry.get("purpose") or ""
        href = f'/catalog#{task_slug(entry["group"])}' if entry.get("group") else "/catalog"
        thumb = f'img/catalog/{task_slug(entry["group"])}.webp' if entry.get("group") else ""
        cards.append(
            f'<a class="deliverable gb spot" href="{escape(href)}">{_thumb(thumb)}<div class="deliverable-copy">'
            f'<span class="art-icon">{icon(ARTIFACT_ICONS.get(item.get("id"), "file-text"))}</span>'
            f'<h3>{escape(title)}</h3><p>{escape(purpose)}</p></div></a>'
        )
    return f'<div class="deliverable-grid">{"".join(cards)}</div><div class="hero-actions"><a class="btn primary" href="/chat">{icon("message-circle")}Generate them in chat</a></div>'


def _thumb(path):
    return art.img(path, "thumb") if path and art.exists(path) else ""


def _deliverables(demo):
    cards = []
    for item in demo.get("artifacts") or []:
        key = escape(item["id"])
        kind = ".pptx" if item["id"] == "deck" else ".html"
        cards.append(
            f"""<article class="deliverable gb spot{' hero' if item['id'] == 'deck' else ''}" data-card="{key}">
  <button type="button" class="thumb-btn" data-artifact="{key}" aria-label="View the {escape(item['title'])}">{_thumb(item.get("thumb"))}</button>
  <div class="deliverable-copy">
    <h3>{escape(item["title"])}</h3>
    <p>{escape(item.get("purpose") or "")}</p>
    <div class="deliverable-actions">
      <button type="button" class="btn small primary" data-artifact="{key}">{icon("eye")}View</button>
      <button type="button" class="btn small ghost" data-open="{key}">{icon("external-link")}Full page</button>
      <button type="button" class="btn small ghost" data-save="{key}" data-kind="{kind}">{icon("download")}{kind}</button>
      <button type="button" class="linkish" data-save="{key}" data-kind=".md">.md</button>
    </div>
  </div>
</article>"""
        )
    return f"""<div class="deliverable-grid live">{"".join(cards)}</div>
<div class="viewer card" id="viewer" hidden>
  <header class="viewer-head"><p class="kicker" id="viewer-kicker">Deliverable</p><h3 id="viewer-title"></h3><div class="deliverable-actions" id="viewer-actions"></div></header>
  <iframe id="viewer-frame" title="Deliverable preview" loading="lazy"></iframe>
</div>
<div class="more-artifacts">
  <h3 class="sub-head">More from the catalog</h3>
  <p class="muted">Each one is written by a model from this engagement and opens here as a styled page.</p>
  <div class="chips" id="catalog-picks"></div>
  <p class="status-line" id="artifact-status" role="status"></p>
</div>"""

"""A finished /chat engagement as the demo report, plus its consulting deliverables (HTML documents and the deck spec)."""
import re
from datetime import date
from html import escape

from .artifact_doc import document
from .chatjob import MATURITY, MATURITY_MEANING, WINDOWS, frame_markdown, load_state, method_lines, plan_markdown
from .harnesskit import kit_files
from .skillpack import pack_manifest

OWNERS = ("Human", "Hybrid", "AI Agent")

DELIVERABLES = (
    ("deck", "Client deck", "The whole engagement as slides your team can present. Opens as PowerPoint.", "img/catalog/deck-and-exhibit-production.webp"),
    ("exec-memo", "Executive memo", "The partner's memo: the question, the decisions required, five moves, the options weighed, value at stake, the risk register, and the first 90 days.", "img/catalog/synthesis-and-recommendations.webp"),
    ("work-chart", "Work chart", "Every step in swimlanes, with who owns it today and in the agent era.", "img/what-you-get/work-chart.webp"),
    ("research-brief", "Research brief", "Every source the research agents read, with the note they kept.", "img/what-you-get/research-brief.webp"),
    ("roadmap", "Roadmap", "Now, next, later, the Top 5 by impact and effort, the 90-day milestones with owners and gates, and the measures.", "img/catalog/program-management.webp"),
)
ART = {
    "cover": "img/brand/hero.webp",
    "market": "img/what-you-get/market-analysis.webp",
    "panel": "img/what-you-get/expert-panel.webp",
    "build": "img/what-you-get/harness-kit.webp",
}


def ready(state):
    return bool(state.get("chart") and state.get("panel") and state.get("top5") and state.get("maturity") in MATURITY)


def clean(text):
    text = re.sub(r"^[#>\s*-]+", "", str(text or ""))
    return " ".join(text.split())


def step_name(step):
    name = clean(step.get("step"))
    return "" if not name or name.isdigit() else name


def title_of(state):
    return state.get("service_line") or (state.get("panel") or {}).get("service_line") or "Your engagement"


def sources(state):
    """Brief citations first, then every other page the research agents read."""
    by_url = {s["url"]: s for s in state.get("sources") or []}
    rows, seen = [], set()
    for item in (state.get("brief") or {}).get("citations") or []:
        source = by_url.get(item["url"]) or {}
        note = clean(source.get("content")) if len(clean(source.get("content"))) > len(clean(item.get("note"))) else clean(item.get("note"))
        rows.append({"title": item["title"], "url": item["url"], "note": note, "date": source.get("date") or "", "cited": True})
        seen.add(item["url"])
    for source in state.get("sources") or []:
        if source["url"] not in seen:
            rows.append({"title": source["title"], "url": source["url"], "note": clean(source.get("content")), "date": source.get("date") or "", "cited": False})
            seen.add(source["url"])
    return rows


def _skills(state):
    try:
        manifest = pack_manifest(state)
    except ValueError:
        return [], []
    skills = [{"name": s["name"], "description": s["description"]} for s in manifest["skills"]]
    try:
        paths = sorted(kit_files(state))
    except ValueError:
        paths = []
    return skills, paths


def live_demo(raw):
    """The demo-report dict for a finished live engagement, so /chat renders through the /demos renderer."""
    state = load_state(raw)
    if not ready(state):
        raise ValueError("not ready")
    panel = state["panel"]
    attacks = state.get("attacks") or {}
    said = {}
    for row in state["debate"]:
        said.setdefault(row["name"], []).append(row)
    experts = [
        {
            "name": e["name"],
            "role": e["role"],
            "lens": e["lens"],
            "insight": e["insight"],
            "recommendation": e["recommendation"],
            "said": said.get(e["name"], []),
        }
        for e in state["experts"]
    ]
    blind = ([panel["dissent"]] if panel.get("dissent") else []) + [
        f'{a["threat"]}. {a["why"]}'.strip() for a in attacks.get("attacks") or []
    ]
    steps = [
        {"priority": label, "step_description": text, "suggested_rationale": ""}
        for label, key in (("Now", "now"), ("Next", "next"), ("Later", "later"))
        for text in panel[key]
    ]
    skills, paths = _skills(state)
    chart = {
        "summary": state["chart"]["summary"],
        "current": [dict(s, step=step_name(s) or s["task"], task="" if not step_name(s) else s["task"]) for s in state["chart"]["current"]],
        "future": [dict(s, step=step_name(s) or s["task"], task="" if not step_name(s) else s["task"]) for s in state["chart"]["future"]],
    }
    return {
        "live": True,
        "slug": "live",
        "company": title_of(state),
        "problem": state["problem"],
        "team": state.get("team") or "",
        "tools": state.get("tools") or "",
        "market": {"summary": (state.get("brief") or {}).get("summary") or "", "citations": sources(state)},
        "experts": experts,
        "debate": state["debate"],
        "synthesis": {
            "cohesive_summary": panel["consensus"],
            "key_themes": [f'{p["name"]}, {p["title"]}. {p["recommendation"]}' for p in panel["personas"]],
            "potential_blind_spots": blind,
            "actionable_next_steps": steps,
            "judges": panel["personas"],
            "red_team": attacks or None,
        },
        "top5": state["top5"],
        "maturity": {"score": state["maturity"], "reason": f'{MATURITY[state["maturity"]]}. {MATURITY_MEANING[state["maturity"]]}'},
        "chart": chart,
        "skills": [s["name"] for s in skills],
        "kit_files": {"paths": paths, "skills": skills},
        "artifacts": [{"id": key, "title": title, "purpose": text, "thumb": thumb} for key, title, text, thumb in DELIVERABLES],
        "catalog": sorted(state.get("artifacts") or {}),
        "art": ART,
        "frame": state.get("frame"),
        "plan": state.get("plan"),
        "method": method_lines(state),
    }


# ---------- standalone documents ----------

def _img(base, path, cls=""):
    klass = f' class="{cls}"' if cls else ""
    return f'<img{klass} src="{escape(base)}/{escape(path)}" alt="" loading="lazy">'


def _wrap(tag, text):
    return f"<{tag}>{escape(text)}</{tag}>" if text else ""


def _owner(raw):
    value = (raw or "Human").lower()
    cls = "agent" if "agent" in value else ("hybrid" if "hybrid" in value else "human")
    return f'<span class="own {cls}">{escape(raw or "Human")}</span>'


def _chips(item):
    return "".join(
        f'<span class="lvl" data-v="{escape(item[key])}"><small>{label}</small>{escape(item[key])}</span>'
        for label, key in (("Confidence", "confidence"), ("Impact", "impact"), ("Effort", "effort"))
    )


def _host(url):
    return url.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")


def memo_html(state, base=""):
    panel = state["panel"]
    cites = sources(state)[:12]
    recs = "".join(
        f"""<li><h3>{escape(t["title"])}</h3><p>{escape(t["detail"])}</p>
<p class="meta">{_chips(t)}<span class="lvl"><small>Backed by</small>{len(t["backers"])} of {len(state["experts"])}</span></p></li>"""
        for t in state["top5"]
    )
    risks = ""
    attacks = (state.get("attacks") or {}).get("attacks") or []
    rows = [(a["threat"], a["mitigation"]) for a in attacks]
    for t in state["top5"]:
        for d in t["dissenters"][:1]:
            rows.append((f'{d["name"]} on "{t["title"]}"', d["why"]))
    if panel.get("dissent"):
        rows.insert(0, ("The main dissent", panel["dissent"]))
    if rows:
        risks = "<h2>Risks and dissent</h2><table class=\"risk\"><thead><tr><th>Risk</th><th>How we handle it</th></tr></thead><tbody>" + "".join(
            f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in rows[:6]
        ) + "</tbody></table>"
    phases = "".join(
        f'<div><h4>{label}</h4><ul>{"".join(f"<li>{escape(x)}</li>" for x in panel[key])}</ul></div>'
        for label, key in (("Now", "now"), ("Next", "next"), ("Later", "later"))
    )
    plan = state.get("plan") or {}
    for r in plan.get("risks") or []:
        rows.append((f'{r["risk"]} ({r["likelihood"]} likelihood, {r["impact"]} impact)', r["mitigation"] + (f' Owner: {r["owner"]}.' if r["owner"] else "")))
    if rows:
        risks = "<h2>Risks and dissent</h2><table class=\"risk\"><thead><tr><th>Risk</th><th>How we handle it</th></tr></thead><tbody>" + "".join(
            f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in rows[:10]
        ) + "</tbody></table>"
    notes = "".join(f'<li>{escape(c["title"])}. <a href="{escape(c["url"])}">{escape(_host(c["url"]))}</a></li>' for c in cites)
    score = state["maturity"]
    frame = state.get("frame") or {}
    decisions = ""
    if plan.get("decisions"):
        decisions = "<h2>Decisions we need from you</h2><ol class=\"decisions\">" + "".join(
            f'<li><b>{escape(_sentence(d["decision"]))}</b>{escape(" Owner: " + _sentence(d["owner"])) if d["owner"] else ""}{escape(" By: " + _sentence(d["by_when"])) if d["by_when"] else ""}</li>'
            for d in plan["decisions"]
        ) + "</ol>"
    question = ""
    if frame:
        parts = "".join(f"<p><b>{label}.</b> {escape(text)}</p>" for label, text in (("Situation", frame["situation"]), ("Complication", frame["complication"]), ("Question", frame["key_question"])) if text)
        options = "".join(
            f'<tr><td>{escape(o["name"])}</td><td><span class="lvl" data-v="{_verdict_level(o["verdict"])}">{escape(o["verdict"])}</span></td><td>{escape(o["summary"])} {escape(o["why"])}</td></tr>'
            for o in frame["options"]
        )
        question = f'<h2>The question we answered</h2>{parts}<h2>Options considered</h2><table class="risk options"><thead><tr><th>Option</th><th>Verdict</th><th>Why</th></tr></thead><tbody>{options}</tbody></table>'
    value = ""
    if frame.get("value_drivers"):
        value = "<h2>Value at stake</h2><ul class=\"drivers\">" + "".join(
            f'<li><b>{escape(v["driver"])}.</b> {escape(v["mechanism"])}{escape(" How to size it: " + v["how_to_size"]) if v["how_to_size"] else ""}</li>' for v in frame["value_drivers"]
        ) + "</ul><p class=\"muted\">Figures that are not in the cited sources are assumptions for your finance team to size.</p>"
    ninety = ""
    if plan.get("milestones"):
        ninety = "<h2>The first 90 days</h2><table class=\"risk plan\"><thead><tr><th>Window</th><th>Milestone</th><th>Owner</th><th>Decision gate</th></tr></thead><tbody>" + "".join(
            f'<tr><td>{escape(m["window"])}</td><td>{escape(m["milestone"])}</td><td>{escape(m["owner"] or "-")}</td><td>{escape(m["gate"] or "-")}</td></tr>' for m in plan["milestones"]
        ) + "</tbody></table>"
        if plan.get("cadence"):
            ninety += f'<p><b>Cadence.</b> {escape(plan["cadence"])}</p>'
    measures = ""
    if plan.get("kpis"):
        measures = "<h2>How we will know it is working</h2><table class=\"risk kpis\"><thead><tr><th>Measure</th><th>Direction</th><th>Cadence</th><th>Why</th></tr></thead><tbody>" + "".join(
            f'<tr><td>{escape(k["metric"])}</td><td>{escape(k["direction"])}</td><td>{escape(k["cadence"] or "-")}</td><td>{escape(k["why"])}</td></tr>' for k in plan["kpis"]
        ) + "</tbody></table>"
    people = ""
    if plan.get("stakeholders"):
        people = "<h2>Who needs to be aligned</h2><table class=\"risk people\"><thead><tr><th>Who</th><th>Role</th><th>What they need</th></tr></thead><tbody>" + "".join(
            f'<tr><td>{escape(p["who"])}</td><td>{escape(p["role"])}</td><td>{escape(p["needs"])}</td></tr>' for p in plan["stakeholders"]
        ) + "</tbody></table>"
    assumptions = ""
    if frame.get("assumptions") or frame.get("open_questions"):
        items = "".join(f"<li><b>Must be true.</b> {escape(a)}</li>" for a in frame.get("assumptions") or []) + "".join(
            f'<li><b>Open.</b> {escape(q["question"])}{escape(" " + q["how_to_answer"]) if q["how_to_answer"] else ""}</li>' for q in frame.get("open_questions") or []
        )
        assumptions = f'<h2>Assumptions and open questions</h2><ul class="drivers">{items}</ul>'
    method = "<h2>How this engagement was run</h2><ul class=\"drivers method\">" + "".join(f"<li>{escape(line)}</li>" for line in method_lines(state)) + "</ul>"
    body = f"""<div class="memo">
<p class="kicker red">Memorandum</p>
<h1>{escape(title_of(state))}</h1>
<dl class="memo-meta">
  <dt>To</dt><dd>Leadership team{escape(", " + state["team"]) if state.get("team") else ""}</dd>
  <dt>From</dt><dd>AI Partner engagement team: research agents, a panel of {len(state["experts"])} AI experts, and a judge</dd>
  <dt>Date</dt><dd>{escape(date.today().strftime("%B %-d, %Y"))}</dd>
  <dt>Re</dt><dd>{escape(clean(state["problem"])[:300])}</dd>
</dl>
<hr class="rule">
<h2>Bottom line</h2>
<p class="lead">{escape(panel["consensus"])}</p>
{decisions}
{question}
<h2>What we recommend</h2>
<ol class="memo-recs">{recs}</ol>
{value}
<h2>What the research says</h2>
<p>{escape((state.get("brief") or {}).get("summary") or "")}</p>
{risks}
<h2>Next steps</h2>
<div class="phases">{phases}</div>
{ninety}
{measures}
{people}
{assumptions}
<h2>Where the team stands</h2>
<p>AI maturity <b>{score} of 4, {escape(MATURITY[score])}</b>. {escape(MATURITY_MEANING[score])}</p>
{method}
<section class="notes"><h4>Sources</h4><ol>{notes}</ol></section>
</div>"""
    return document("Executive memo · " + title_of(state), "Executive memo", body, "memo-doc")


def _sentence(text):
    """End a fragment with one full stop, never two."""
    text = clean(text)
    return text if not text or text[-1] in ".!?" else text + "."


def _verdict_level(verdict):
    """Map an option verdict onto the level palette: recommended is high, conditional medium, rejected low."""
    return {"recommended": "high", "conditional": "medium"}.get(verdict, "low")


def swimlane(chart):
    lanes = "".join(f'<div class="lane-head {o.split()[-1].lower()}">{_owner(o)}</div>' for o in OWNERS)
    rows = []
    for n, step in enumerate(chart["future"], 1):
        name = step_name(step)
        card = f'<div class="step"><span class="n">{n:02d}</span><b>{escape(name or step["task"])}</b>{_wrap("p", step["task"] if name else "")}{_owner(step["owner"])}</div>'
        cells = "".join(card if step["owner"] == owner else '<div class="gap" aria-hidden="true"></div>' for owner in OWNERS)
        rows.append(f'<div class="swim-row">{cells}</div>')
    return f'<div class="swim"><div class="swim-row heads">{lanes}</div>{"".join(rows)}</div>'


def _tally(chart):
    counts = {o: sum(1 for s in chart["future"] if s["owner"] == o) for o in OWNERS}
    return "".join(f'<div class="tally-box {o.split()[-1].lower()}"><b>{counts[o]}</b><span>{o}</span></div>' for o in OWNERS)


def workchart_html(state, base=""):
    chart = state["chart"]
    today = "".join(
        f'<tr><td class="n">{n:02d}</td><td><b>{escape(step_name(s) or s["task"])}</b>{_wrap("span", s["task"] if step_name(s) else "")}</td><td>{_owner(s["owner"])}</td></tr>'
        for n, s in enumerate(chart["current"], 1)
    )
    handed = sum(1 for s in chart["future"] if s["owner"] != "Human")
    body = f"""<p class="kicker"><b class="red">Work chart</b> · {len(chart["current"])} steps today, {handed} of {len(chart["future"])} with agents</p>
<h1>Who owns each step, <em>today and with agents.</em></h1>
<p class="lead">{escape(chart["summary"])}</p>
<div class="tally">{_tally(chart)}</div>
<h2>Agent era</h2>
{swimlane(chart)}
<h2>Today</h2>
<table class="today"><thead><tr><th>#</th><th>Step</th><th>Owner</th></tr></thead><tbody>{today}</tbody></table>
<p class="legend">{_owner("Human")} judgment, a relationship, or accountability. {_owner("Hybrid")} an agent drafts and a person approves. {_owner("AI Agent")} the step runs without a person.</p>"""
    return document("Work chart · " + title_of(state), "Work chart", body, "chart-doc")


def brief_html(state, base=""):
    rows = "".join(
        f"""<li><p class="src"><span>{n:02d}</span>{escape(_host(c["url"]))}{" · " + escape(c["date"][:10]) if c["date"] else ""}{'<b class="cited">Cited</b>' if c["cited"] else ""}</p>
<h3><a href="{escape(c["url"])}">{escape(c["title"])}</a></h3><p>{escape(c["note"])}</p></li>"""
        for n, c in enumerate(sources(state), 1)
    )
    queries = "".join(f"<span>{escape(q)}</span>" for q in state.get("queries") or [])
    body = f"""<p class="kicker"><b class="red">Research brief</b> · {len(sources(state))} sources</p>
<h1>What the public record says.</h1>
{_img(base, "img/what-you-get/research-brief.webp", "doc-art")}
<p class="lead">{escape((state.get("brief") or {}).get("summary") or "")}</p>
{f'<div class="queries"><small>Searches</small>{queries}</div>' if queries else ""}
<ol class="source-list">{rows}</ol>"""
    return document("Research brief · " + title_of(state), "Research brief", body, "brief-doc")


def matrix(top5):
    cells = {}
    for n, t in enumerate(top5, 1):
        cells.setdefault((t["impact"], t["effort"]), []).append((n, t["confidence"]))
    grid = []
    for impact in ("high", "medium", "low"):
        for effort in ("low", "medium", "high"):
            dots = "".join(f'<span class="dot {c}">{n}</span>' for n, c in cells.get((impact, effort), []))
            best = " best" if impact == "high" and effort == "low" else ""
            grid.append(f'<div class="cell{best}">{dots}</div>')
    return f"""<div class="matrix"><span class="y">Impact →</span><div class="grid">{"".join(grid)}</div>
<div class="ticks-y"><span>High</span><span>Med</span><span>Low</span></div><div class="ticks-x"><span>Low</span><span>Medium</span><span>High</span></div><span class="x">Effort →</span></div>"""


def roadmap_html(state, base=""):
    panel = state["panel"]
    cols = "".join(
        f'<section class="phase {key}"><p class="kicker">{label}</p><ol>{"".join(f"<li>{escape(x)}</li>" for x in panel[key])}</ol></section>'
        for label, key in (("Now", "now"), ("Next", "next"), ("Later", "later"))
    )
    recs = "".join(f'<li><span class="n">{n}</span><b>{escape(t["title"])}</b><span class="chips">{_chips(t)}</span></li>' for n, t in enumerate(state["top5"], 1))
    plan = state.get("plan") or {}
    ninety = ""
    if plan.get("milestones"):
        windows = "".join(
            f'<section class="phase"><p class="kicker">{escape(window)}</p><ol>'
            + "".join(f'<li><b>{escape(m["milestone"])}</b>{escape(" (" + m["owner"] + ")") if m["owner"] else ""}{escape(" Gate: " + m["gate"]) if m["gate"] else ""}</li>' for m in plan["milestones"] if m["window"] == window)
            + "</ol></section>"
            for window in WINDOWS
        )
        ninety = f'<h2>The first 90 days</h2><div class="phases big">{windows}</div>' + (f'<p><b>Cadence.</b> {escape(plan["cadence"])}</p>' if plan.get("cadence") else "")
    measures = ""
    if plan.get("kpis"):
        measures = "<h2>How we will know</h2><table class=\"risk kpis\"><thead><tr><th>Measure</th><th>Direction</th><th>Cadence</th><th>Why</th></tr></thead><tbody>" + "".join(
            f'<tr><td>{escape(k["metric"])}</td><td>{escape(k["direction"])}</td><td>{escape(k["cadence"] or "-")}</td><td>{escape(k["why"])}</td></tr>' for k in plan["kpis"]
        ) + "</tbody></table>"
    decisions = ""
    if plan.get("decisions"):
        decisions = "<h2>Decisions that unlock it</h2><ol class=\"decisions\">" + "".join(
            f'<li><b>{escape(_sentence(d["decision"]))}</b>{escape(" Owner: " + _sentence(d["owner"])) if d["owner"] else ""}{escape(" By: " + _sentence(d["by_when"])) if d["by_when"] else ""}</li>' for d in plan["decisions"]
        ) + "</ol>"
    body = f"""<p class="kicker"><b class="red">Roadmap</b> · now, next, later</p>
<h1>What to do first, <em>and what waits.</em></h1>
<p class="lead">{escape(panel["consensus"])}</p>
<div class="phases big">{cols}</div>
<h2>The Top 5 by impact and effort</h2>
<div class="rm-grid">{matrix(state["top5"])}<ol class="rm-recs">{recs}</ol></div>
{decisions}
{ninety}
{measures}"""
    return document("Roadmap · " + title_of(state), "Roadmap", body, "roadmap-doc")


# ---------- the deck: one slide spec, rendered to HTML here and to .pptx in deck_pptx ----------

def _cut(text, limit):
    text = clean(text)
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def slides(state):
    panel = state["panel"]
    top5 = state["top5"]
    cites = sources(state)
    frame = state.get("frame") or {}
    plan = state.get("plan") or {}
    challenge = [d for d in state["debate"] if d["stance"] == "challenge"] or state["debate"]
    section = {"n": 0}

    def k(label):
        section["n"] += 1
        return f"{section['n']:02d} · {label}"

    out = [
        {"kind": "cover", "kicker": "AI Partner · Strategy engagement", "title": title_of(state), "sub": _cut(state["problem"], 220), "art": ART["cover"]},
        {"kind": "bullets", "kicker": k("Executive summary"), "title": "The bottom line", "lede": panel["consensus"], "bullets": [t["title"] for t in top5], "numbered": True},
    ]
    if plan.get("decisions"):
        out.append({"kind": "bullets", "kicker": k("Decisions required"), "title": "What we need you to decide", "bullets": [_sentence(d["decision"]) + (f' Owner: {_sentence(d["owner"])}' if d["owner"] else "") + (f' By {_sentence(d["by_when"])}' if d["by_when"] else "") for d in plan["decisions"]], "numbered": True})
    if frame:
        out.append({"kind": "bullets", "kicker": k("The question"), "title": _cut(frame["key_question"], 110), "bullets": [f"Situation. {frame['situation']}" if frame["situation"] else "", f"Complication. {frame['complication']}" if frame["complication"] else "", f"Question. {frame['key_question']}"]})
        out[-1]["bullets"] = [b for b in out[-1]["bullets"] if b]
        out.append({"kind": "table", "kicker": k("Options considered"), "title": "Three paths, one recommendation", "head": ["#", "Option", "Verdict", "Why"], "widths": [0.5, 3.4, 1.6, 6.4], "levels": (2,), "rows": [[str(n), _cut(o["name"] + ". " + o["summary"], 140), o["verdict"], _cut(o["why"] or o["downside"], 150)] for n, o in enumerate(frame["options"], 1)]})
    out += [
        {"kind": "bullets", "kicker": k(f"Research · {len(cites)} sources"), "title": "What the public record says", "lede": _cut((state.get("brief") or {}).get("summary"), 300), "bullets": [f'{_cut(c["title"], 70)} ({_host(c["url"])})' for c in cites[:4]], "art": ART["market"]},
        {"kind": "grid", "kicker": k(f"The panel · {len(state['experts'])} AI experts"), "title": "Twenty lenses on one problem", "items": [(e["name"], _cut(e["role"], 48)) for e in state["experts"]]},
        {"kind": "bullets", "kicker": k(f"Debate · {len(state['debate'])} statements, two rounds"), "title": "Where the panel pushed back", "bullets": [f'{d["name"]} to {d["responding_to"] or "the panel"}: {_cut(d["statement"], 200)}' for d in challenge[:4]]},
        {"kind": "table", "kicker": k("Top 5"), "title": "Five moves, in the judge's order", "head": ["#", "Recommendation", "Impact", "Effort", "Confidence", "Backers"], "rows": [[str(n), _cut(t["title"], 110), t["impact"], t["effort"], t["confidence"], str(len(t["backers"]))] for n, t in enumerate(top5, 1)]},
    ]
    for n, t in enumerate(top5, 1):
        dissent = t["dissenters"][0] if t["dissenters"] else None
        out.append({
            "kind": "rec", "kicker": f"Recommendation {n} of {len(top5)}", "n": n, "title": t["title"], "detail": t["detail"],
            "levels": [("Confidence", t["confidence"]), ("Impact", t["impact"]), ("Effort", t["effort"])],
            "backers": t["backers"], "dissent": f'{dissent["name"]}: {dissent["why"]}' if dissent else "",
        })
    if frame.get("value_drivers"):
        out.append({"kind": "bullets", "kicker": k("Value at stake"), "title": "Where the value comes from", "lede": "Each driver names the mechanism and the inputs your finance team needs to size it. No figure here is invented.", "bullets": [f'{v["driver"]}. {v["mechanism"]}' + (f' Size it with {v["how_to_size"]}' if v["how_to_size"] else "") for v in frame["value_drivers"]]})
    if plan.get("risks"):
        out.append({"kind": "table", "kicker": k("Risk register"), "title": "What could go wrong, and who watches it", "head": ["#", "Risk", "Likelihood", "Impact", "Mitigation", "Owner"], "widths": [0.5, 3.3, 1.2, 1.1, 4.2, 1.6], "levels": (2, 3), "rows": [[str(n), _cut(r["risk"], 110), r["likelihood"], r["impact"], _cut(r["mitigation"], 130), _cut(r["owner"] or "-", 28)] for n, r in enumerate(plan["risks"], 1)]})
    out.append({"kind": "chart", "kicker": k("Work chart"), "title": "Who owns each step with agents", "lede": _cut(state["chart"]["summary"], 260), "steps": [(step_name(s) or _cut(s["task"], 120), _cut(s["task"], 110) if step_name(s) else "", s["owner"]) for s in state["chart"]["future"]]})
    out.append({"kind": "columns", "kicker": k("Roadmap"), "title": "Now, next, later", "cols": [(label, panel[key]) for label, key in (("Now", "now"), ("Next", "next"), ("Later", "later"))]})
    if plan.get("milestones"):
        out.append({"kind": "columns", "kicker": k("First 90 days"), "title": "Milestones, owners, and the gates they unlock", "cols": [(window, [f'{m["milestone"]}' + (f' ({m["owner"]})' if m["owner"] else "") + (f'. Gate: {m["gate"]}' if m["gate"] else "") for m in plan["milestones"] if m["window"] == window] or ["No milestone in this window."]) for window in WINDOWS]})
    if plan.get("kpis"):
        out.append({"kind": "table", "kicker": k("Measures"), "title": "How we will know it is working", "head": ["#", "Measure", "Direction", "Cadence", "Why"], "widths": [0.5, 3.6, 1.3, 1.6, 4.9], "levels": (2, 3), "rows": [[str(n), _cut(x["metric"], 90), x["direction"], _cut(x["cadence"] or "-", 20), _cut(x["why"], 150)] for n, x in enumerate(plan["kpis"], 1)]})
    if plan.get("stakeholders"):
        out.append({"kind": "table", "kicker": k("Stakeholders"), "title": "Who needs to be aligned", "head": ["#", "Who", "Role", "What they need"], "widths": [0.5, 3.0, 1.5, 6.9], "levels": (2,), "rows": [[str(n), _cut(x["who"], 60), x["role"], _cut(x["needs"], 170)] for n, x in enumerate(plan["stakeholders"], 1)]})
    if frame.get("assumptions") or frame.get("open_questions"):
        out.append({"kind": "bullets", "kicker": k("Assumptions and open questions"), "title": "What must be true, and what we would check first", "bullets": [f"Must be true. {a}" for a in frame.get("assumptions") or []] + [f'Open. {q["question"]}' + (f' {q["how_to_answer"]}' if q["how_to_answer"] else "") for q in frame.get("open_questions") or []]})
    score = state["maturity"]
    out.append({"kind": "columns", "kicker": k(f"AI maturity · {score} of 4"), "title": f"Today the team is {MATURITY[score]}", "on": score - 1, "cols": [(f"{v} · {MATURITY[v]}", [MATURITY_MEANING[v]]) for v in sorted(MATURITY)]})
    attacks = state.get("attacks")
    if attacks:
        out.append({"kind": "bullets", "kicker": k("Red team"), "title": _cut(attacks["top_risk"], 90), "bullets": [f'{a["threat"]}. Mitigation: {a["mitigation"]}' for a in attacks["attacks"]]})
    skills, _ = _skills(state)
    out.append({"kind": "bullets", "kicker": "Harness kit", "title": "What your team keeps running", "lede": "One zip: CLAUDE.md, playbook.md, model-routing.md, project-state-schema.md, and the skill pack. Run it in Claude Code, Cursor, or any agent that reads skills.", "bullets": [f'{s["name"]}: {_cut(s["description"], 150)}' for s in skills] or ["The skill pack is written after the size question."], "art": ART["build"]})
    out.append({"kind": "bullets", "kicker": "Appendix", "title": "How this engagement was run", "bullets": method_lines(state)})
    return out


def _slide_html(s, base, index, total):
    head = f'<p class="kicker">{escape(s["kicker"])}</p><h2>{escape(s["title"])}</h2>'
    kind = s["kind"]
    if kind == "cover":
        inner = f'<div class="cover-copy"><p class="kicker">{escape(s["kicker"])}</p><h1>{escape(s["title"])}</h1><p>{escape(s["sub"])}</p></div>{_img(base, s["art"], "cover-art")}'
    elif kind == "bullets":
        tag = "ol" if s.get("numbered") else "ul"
        lede = f'<p class="lede">{escape(s["lede"])}</p>' if s.get("lede") else ""
        items = "".join(f"<li>{escape(b)}</li>" for b in s["bullets"])
        art = _img(base, s["art"], "side-art") if s.get("art") else ""
        inner = f'<div class="copy">{head}{lede}<{tag}>{items}</{tag}></div>{art}'
    elif kind == "grid":
        inner = head + '<div class="people">' + "".join(f"<div><b>{escape(a)}</b><span>{escape(b)}</span></div>" for a, b in s["items"]) + "</div>"
    elif kind == "table":
        rows = "".join("<tr>" + "".join(f'<td data-v="{escape(c)}">{escape(c)}</td>' for c in row) + "</tr>" for row in s["rows"])
        inner = head + "<table><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in s["head"]) + f"</tr></thead><tbody>{rows}</tbody></table>"
    elif kind == "rec":
        levels = "".join(f'<span class="lvl" data-v="{escape(v)}"><small>{escape(k)}</small>{escape(v)}</span>' for k, v in s["levels"])
        backers = "".join(f"<span>{escape(b)}</span>" for b in s["backers"])
        dissent = f'<p class="dissent"><b>Dissent.</b> {escape(s["dissent"])}</p>' if s["dissent"] else ""
        inner = f'<span class="big-n">{s["n"]}</span><div class="copy"><p class="kicker">{escape(s["kicker"])}</p><h2>{escape(s["title"])}</h2><p class="lede">{escape(s["detail"])}</p><p class="meta">{levels}</p><p class="backers"><small>Backed by {len(s["backers"])}</small>{backers}</p>{dissent}</div>'
    elif kind == "chart":
        steps = "".join(f'<li><span class="n">{n:02d}</span><div><b>{escape(a)}</b>{_wrap("span", b)}</div>{_owner(o)}</li>' for n, (a, b, o) in enumerate(s["steps"], 1))
        inner = head + f'<p class="lede">{escape(s["lede"])}</p><ol class="steps">{steps}</ol>'
    else:
        cols = "".join(
            f'<div class="col{" on" if s.get("on") == i else ""}"><h4>{escape(label)}</h4><ul>{"".join(f"<li>{escape(x)}</li>" for x in items)}</ul></div>'
            for i, (label, items) in enumerate(s["cols"])
        )
        inner = head + f'<div class="cols n{len(s["cols"])}">{cols}</div>'
    return f'<section class="slide {kind}"><div class="slide-in">{inner}</div><span class="pg">{index:02d} / {total:02d}</span></section>'


def deck_html(state, base=""):
    spec = slides(state)
    body = f"""<p class="kicker"><b class="red">Client deck</b> · {len(spec)} slides · download the .pptx to present</p>
<div class="deck">{"".join(_slide_html(s, base, i, len(spec)) for i, s in enumerate(spec, 1))}</div>"""
    return document("Client deck · " + title_of(state), "Client deck", body, "deck-doc")


def markdown_for(state, key):
    panel = state["panel"]
    if key == "exec-memo":
        lines = [f"# Executive memo: {title_of(state)}", "", "## Bottom line", "", panel["consensus"], "", "## What we recommend", ""]
        lines += [f'{n}. **{t["title"]}** {t["detail"]} (confidence {t["confidence"]}, impact {t["impact"]}, effort {t["effort"]})' for n, t in enumerate(state["top5"], 1)]
        lines += ["", "## Next steps", ""] + [f"- {label}: {x}" for label, key2 in (("Now", "now"), ("Next", "next"), ("Later", "later")) for x in panel[key2]]
        lines += [""] + frame_markdown(state.get("frame")) + plan_markdown(state.get("plan"))
        lines += ["## How this engagement was run", ""] + [f"- {line}" for line in method_lines(state)]
        return "\n".join(lines) + "\n"
    if key == "work-chart":
        lines = [f"# Work chart: {title_of(state)}", "", state["chart"]["summary"], "", "| # | Step | Task | Owner |", "|---|---|---|---|"]
        lines += [f'| {n} | {step_name(s) or "-"} | {s["task"]} | {s["owner"]} |' for n, s in enumerate(state["chart"]["future"], 1)]
        return "\n".join(lines) + "\n"
    if key == "research-brief":
        lines = [f"# Research brief: {title_of(state)}", "", (state.get("brief") or {}).get("summary") or "", ""]
        lines += [f'{n}. [{c["title"]}]({c["url"]}). {c["note"]}' for n, c in enumerate(sources(state), 1)]
        return "\n".join(lines) + "\n"
    if key == "roadmap":
        lines = [f"# Roadmap: {title_of(state)}", ""]
        for label, key2 in (("Now", "now"), ("Next", "next"), ("Later", "later")):
            lines += [f"## {label}", ""] + [f"- {x}" for x in panel[key2]] + [""]
        plan = state.get("plan")
        if plan:
            lines += [line for line in plan_markdown(plan) if not line.startswith("## Risk register")]
        return "\n".join(lines)
    lines = [f"# Client deck: {title_of(state)}", ""]
    for s in slides(state):
        lines += [f'## {s["title"]}', ""]
    return "\n".join(lines)


BUILDERS = {"deck": deck_html, "exec-memo": memo_html, "work-chart": workchart_html, "research-brief": brief_html, "roadmap": roadmap_html}


def deliverables(raw, base=""):
    state = load_state(raw)
    if not ready(state):
        raise ValueError("not ready")
    return [
        {"id": key, "title": title, "html": BUILDERS[key](state, base), "markdown": markdown_for(state, key), "pptx": key == "deck"}
        for key, title, _, _ in DELIVERABLES
    ]

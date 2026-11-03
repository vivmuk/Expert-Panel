"""Shared page shell, the connect pill, the catalog and What you get pages."""
import re
from html import escape

from .. import art
from ..catalog import groups
from ..deliverables import DELIVERABLES
from ..icons import icon

NAV_ITEMS = (
    ("/chat", "message-circle", "Chat"),
    ("/demos", "layers", "Demos"),
    ("/what-you-get", "package", "What you get"),
    ("/catalog", "book-open", "Catalog"),
    ("/about", "monitor-play", "About"),
)

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400..800&family=JetBrains+Mono:wght@400..700&display=swap">'
)

HARNESS_MARKS = (
    ("/img/marks/claude.svg", "Claude"),
    ("/img/marks/openai-blossom.svg", "ChatGPT"),
    ("/img/marks/cursor.svg", "Cursor"),
    ("/img/marks/claude-code.png", "Claude Code"),
    ("/img/marks/gemini.svg", "Gemini"),
    ("/img/marks/copilot.svg", "GitHub Copilot"),
    ("/img/marks/opencode.png", "OpenCode"),
    ("/img/marks/muse.svg", "Muse"),
)


def head(title, extra=""):
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(title)}</title>
<meta name="description" content="Your team describes a business problem. AI Partner agents research it, a panel of 20 AI experts debates it, and you get the Top 5 moves, a work chart, and the harness kit. Your first engagement is free.">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-512.png" sizes="512x512" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#FAFAF7">
{FONTS}
<link rel="stylesheet" href="/app.css">
{extra}<script src="/motion.js" defer></script>"""


def nav(current=""):
    links = []
    for href, name, label in NAV_ITEMS:
        here = ' aria-current="page"' if href == current else ""
        links.append(f'<a href="{href}"{here}>{icon(name)}<span>{label}</span></a>')
    here = ' aria-current="page"' if current == "/connect" else ""
    links.append(f'<a class="cta gb" href="/connect"{here}>{icon("plug")}<span>Connect</span></a>')
    return '<nav class="links" aria-label="Main">' + "".join(links) + "</nav>"


NAV = nav()

# Infrastructure the running agent actually uses. Wording stays "Built on":
# a credit, not a partnership or sponsorship claim.
BUILT_ON = (
    ("https://maritime.sh", "Maritime", "Hosts the agent."),
    ("https://supermemory.ai", "Supermemory", "Memory across engagements."),
    ("https://onkeiki.com", "Keiki", "iMessage and email channel."),
    ("https://venice.ai", "Venice", "Model inference."),
    ("https://exa.ai", "Exa", "Market research search."),
    ("https://railway.com", "Railway", "Backup host."),
)


def _built_on_link(href, name):
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{escape(name)}</a>'


def built_on_strip():
    links = " · ".join(_built_on_link(href, name) for href, name, _line in BUILT_ON)
    return f'<p class="built-on">Built on {links}</p>'


def built_on_section():
    items = "".join(
        f"<li>{_built_on_link(href, name)}<span>{escape(line)}</span></li>"
        for href, name, line in BUILT_ON
    )
    return (
        '<section class="built-on-section" aria-labelledby="built-on-title">'
        '<h2 id="built-on-title">Built on</h2>'
        f'<ul class="built-on-list">{items}</ul>'
        "</section>"
    )


def header(current=""):
    return (
        '<a class="skip" href="#main">Skip to content</a>'
        '<header class="top"><a class="brand" href="/chat" aria-label="AI Partner, home">'
        '<img class="persona" src="/img/brand/avatar.webp" alt="" width="32" height="32">'
        f"<span>AI Partner</span></a>{nav(current)}</header>"
    )


FOOT = f"""
<footer class="site-foot">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="24" height="24"><span>AI Partner</span></a>
  <p class="foot-note">Your team directs the agents. Your first engagement is free.</p>
  <p class="foot-credits">Messaging channels: <a href="https://onkeiki.com" target="_blank" rel="noopener noreferrer"><img src="/img/marks/keiki.svg" alt="" width="14" height="14" loading="lazy" decoding="async">Integrated with Keiki</a></p>
  <nav class="foot-links" aria-label="Footer">
    <a href="/demos">Demos</a><a href="/what-you-get">What you get</a><a href="/catalog">Catalog</a><a href="/about">About</a><a href="/deck">Deck</a><a href="/connect">Connect</a><a href="/get-started.md">get-started.md</a><a href="/keiki.md">keiki.md</a>
  </nav>
  {built_on_strip()}
</footer>
"""


def connect_pill(origin):
    """The 'Connect your own agent' pill: harness marks, the one-line instruction, and a copy button."""
    origin = origin.rstrip("/")
    line = f"Fetch {origin}/get-started.md and follow it"
    marks = "".join(
        f'<img src="{src}" alt="" width="22" height="22" loading="lazy" decoding="async" title="{escape(name)}">'
        for src, name in HARNESS_MARKS
    )
    names = ", ".join(name for _, name in HARNESS_MARKS) + ", and Grok Bot"
    return f"""<div class="pill-row">
  <a class="connect-pill gb spot" href="/connect">
    <span class="pill-marks" role="img" aria-label="Works with {escape(names)}">{marks}<span class="grok-chip" aria-hidden="true">Grok</span></span>
    <span class="pill-copy"><b>Connect your own agent</b><code>{escape(line)}</code></span>
    {icon("arrow-right", "ico pill-go")}
  </a>
  <button type="button" class="copy-btn" data-copy-text="{escape(line)}." aria-label="Copy the setup line">{icon("copy")}<span class="copied" aria-live="polite"></span></button>
</div>"""


def dots(ghost=False, fixed=False):
    cls = "dots dots-fixed" if fixed else "dots"
    flag = " data-ghost" if ghost else ""
    return f'<canvas class="{cls}" data-dots{flag} aria-hidden="true"></canvas>'


def shell(title, current, body, extra_head="", scripts="", body_class=""):
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head(title, extra_head)}
</head>
<body{cls}>
{header(current)}
<main class="wrap" id="main">
{body}
</main>
{FOOT}
{scripts}<script src="/onboard.js" defer></script>
<script src="/voice.js"></script>
</body>
</html>
"""


_shell = shell


def page_head(kicker, title, lede, extra=""):
    return f"""<section class="page-head">
  {dots()}
  <div class="page-head-copy">
    <p class="kicker">{kicker}</p>
    <h1>{title}</h1>
    <p class="lede">{lede}</p>
    {extra}
  </div>
</section>"""


def not_found_page():
    actions = (
        '<div class="hero-actions">'
        f'<a class="btn primary" href="/chat">{icon("message-circle")}Go to the chat</a>'
        f'<a class="btn ghost" href="/demos">{icon("layers")}See the demos</a>'
        "</div>"
    )
    body = page_head("404", "This page isn't here.", "The link may be old or mistyped. The chat and the demos are a click away.", actions)
    return shell("Not found · AI Partner", "", body)


DECK_EMBED_SCRIPT = '<script src="/deck-embed.js" defer></script>\n'


def deck_embed(src, title, heading, kicker="Deck", lede=""):
    """An inline 16:9 deck. deck-embed.js renders it in a fixed 1120x630 viewport scaled to fit, so slides never clip."""
    src = escape(src)
    lede_html = f'<p class="muted">{escape(lede)}</p>' if lede else ""
    return f"""<figure class="deck-embed" data-deck-embed>
  <figcaption class="deck-embed-head">
    <div><p class="kicker">{icon("monitor-play")}{escape(kicker)}</p><h2>{escape(heading)}</h2>{lede_html}</div>
    <div class="deck-embed-actions">
      <button type="button" class="btn small ghost" data-deck-fullscreen>{icon("maximize")}Fullscreen</button>
      <a class="btn small ghost" href="{src}" target="_blank" rel="noopener">{icon("external-link")}Open in new tab</a>
    </div>
  </figcaption>
  <div class="deck-frame">
    <div class="deck-stage">
      <iframe src="{src}" title="{escape(title)}" loading="lazy" allow="fullscreen" allowfullscreen referrerpolicy="same-origin"></iframe>
    </div>
  </div>
  <p class="deck-hint"><span class="hint-keys">Click or tab into the deck, then use <kbd>←</kbd> <kbd>→</kbd> to move between slides. <kbd>Esc</kbd> leaves fullscreen.</span><span class="hint-touch">Swipe the deck to change slides. Tap Fullscreen to read it full size.</span></p>
</figure>"""


ARTIFACT_ICONS = {
    "research-brief": "file-search",
    "market-sizing": "chart-pie",
    "competitive-landscape": "swords",
    "customer-segmentation": "users-round",
    "due-diligence": "clipboard-check",
    "vendor-evaluation": "scale",
    "cost-reduction": "trending-down",
    "pricing-analysis": "badge-dollar-sign",
    "business-case": "briefcase-business",
    "board-one-pager": "presentation",
    "issue-tree": "git-fork",
    "hypothesis-tree": "network",
    "exec-memo": "file-pen-line",
    "interview-guide": "mic",
    "stakeholder-map": "map",
    "workshop": "lightbulb",
    "current-process": "workflow",
    "future-process": "route",
    "operating-model": "boxes",
    "change-plan": "refresh-cw",
    "charter": "scroll-text",
    "scope": "crosshair",
    "workplan": "calendar-range",
    "raci": "grid-3x3",
    "risks": "triangle-alert",
    "roadmap": "milestone",
    "kpi-tree": "gauge",
    "work-chart": "bot",
    "harness-kit": "package",
    "skill-pack": "puzzle",
    "decision-note": "shield-check",
}

TASK_ICONS = (
    "globe", "scale", "badge-dollar-sign", "presentation", "lightbulb",
    "mic", "users", "calendar-range", "shield-check",
)


def task_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _art(folder, slug, glyph, cls):
    path = f"img/{folder}/{slug}.webp"
    if art.exists(path):
        return art.img(path, cls)
    return f'<div class="{cls} art-empty" aria-hidden="true">{icon(glyph, "ico art-glyph")}</div>'


def render_catalog():
    sections = []
    chips = []
    total = 0
    for number, group in enumerate(groups(), 1):
        slug = task_slug(group["task"])
        glyph = TASK_ICONS[(number - 1) % len(TASK_ICONS)]
        cards = []
        for item in group["artifacts"]:
            total += 1
            blob = " ".join([item["title"], item["purpose"], item["group"], item["format"], " ".join(item["sections"])]).lower()
            tags = "".join(f"<li>{escape(name)}</li>" for name in item["sections"][:4])
            cards.append(
                f"""<article class="art-card gb spot reveal" data-artifact="{escape(blob)}">
<span class="art-icon">{icon(ARTIFACT_ICONS.get(item["id"], "file-text"))}</span>
<h3>{escape(item["title"])}</h3>
<p>{escape(item["purpose"])}</p>
<footer><span class="pill">{escape(item["format"])}</span><ul class="tags" aria-label="Sections">{tags}</ul></footer>
</article>"""
            )
        count = len(group["artifacts"])
        chips.append(f'<a class="chip" href="#{slug}">{escape(group["task"])} <span>{count}</span></a>')
        score = int(group["score"])
        sections.append(
            f"""<section class="task" id="{slug}" data-task>
<header class="task-head reveal">
  {_art("catalog", slug, glyph, "task-art")}
  <div class="task-copy">
    <p class="kicker"><b>{number:02d}</b> {count} artifact{"s" if count != 1 else ""}</p>
    <h2>{escape(group["task"])}</h2>
    <p class="score"><span class="meter" role="img" aria-label="Author's assessment {score} of 10"><i style="--v:{score * 10}%"></i></span><span>Author's assessment {score} / 10 · thesis draft, Oct 2026</span></p>
  </div>
</header>
<div class="art-grid">{"".join(cards)}</div>
</section>"""
        )
    search = f"""<div class="search gb">
    {icon("search")}
    <label class="sr-only" for="q">Search artifacts</label>
    <input id="q" type="search" placeholder="Search {total} artifacts, like pricing or risk" autocomplete="off" spellcheck="false">
    <kbd aria-hidden="true">/</kbd>
  </div>
  <p class="search-count" id="q-count" role="status">{total} artifacts in 9 tasks</p>"""
    body = page_head(
        "Catalog",
        "Every artifact a consulting engagement bills for, <em>written by agents</em>.",
        "Nine tasks from the thesis draft, October 2026. Your team picks the artifact; AI Partner agents write it from the engagement.",
        search,
    ) + f"""
<nav class="chips task-chips" aria-label="Tasks">{"".join(chips)}</nav>
{"".join(sections)}
<div class="empty" id="q-empty" hidden>
  {icon("search", "ico empty-glyph")}
  <h2>No artifact matches that.</h2>
  <p>Try a shorter word, like <button type="button" class="linkish" data-q="risk">risk</button> or <button type="button" class="linkish" data-q="process">process</button>.</p>
  <button type="button" class="btn ghost" id="q-clear">Clear search</button>
</div>
<section class="cta-band gb spot reveal">
  <div><p class="kicker">Next</p><h2>Start an engagement and pick artifacts at the end.</h2></div>
  <a class="btn primary" href="/chat">{icon("message-circle")}Start in chat</a>
</section>
<script>
(function () {{
  var q = document.getElementById("q");
  var count = document.getElementById("q-count");
  var empty = document.getElementById("q-empty");
  var total = {total};
  function apply() {{
    var query = q.value.trim().toLowerCase();
    var shown = 0;
    document.querySelectorAll("[data-artifact]").forEach(function (card) {{
      var hit = !query || card.getAttribute("data-artifact").indexOf(query) >= 0;
      card.hidden = !hit;
      if (hit) shown += 1;
    }});
    document.querySelectorAll("[data-task]").forEach(function (section) {{
      section.hidden = !section.querySelector("[data-artifact]:not([hidden])");
    }});
    empty.hidden = shown > 0;
    count.textContent = query ? shown + " of " + total + " artifacts match" : total + " artifacts in 9 tasks";
  }}
  q.addEventListener("input", apply);
  q.addEventListener("keydown", function (e) {{ if (e.key === "Escape") {{ q.value = ""; apply(); q.blur(); }} }});
  document.getElementById("q-clear").addEventListener("click", function () {{ q.value = ""; apply(); q.focus(); }});
  document.querySelectorAll("[data-q]").forEach(function (b) {{
    b.addEventListener("click", function () {{ q.value = b.getAttribute("data-q"); apply(); q.focus(); }});
  }});
  document.addEventListener("keydown", function (e) {{
    var tag = document.activeElement && document.activeElement.tagName;
    if (e.key === "/" && !e.metaKey && !e.ctrlKey && ["INPUT", "TEXTAREA", "SELECT"].indexOf(tag) < 0) {{
      e.preventDefault();
      q.focus();
    }}
  }});
}})();
</script>
"""
    return shell("Catalog · AI Partner", "/catalog", body)


WYG_ICONS = {
    "research-brief": "file-search",
    "market-analysis": "globe",
    "expert-panel": "users",
    "maturity-score": "gauge",
    "work-chart": "workflow",
    "harness-recommendations": "route",
    "harness-kit": "package",
    "skill-pack": "puzzle",
    "mcp-api-access": "plug",
}

FLOW = (
    ("Your team", "Names the problem, the team, the tools, and its AI maturity."),
    ("Research agents", "Run parallel web searches and keep every source URL."),
    ("20 AI experts", "Take distinct lenses and debate the job over two rounds."),
    ("The judge", "Ranks the Top 5 moves with confidence, impact, and effort."),
    ("Your team", "Takes the work chart, harness kit, and skill pack, and decides."),
)


def render_what_you_get():
    cards = []
    for number, item in enumerate(DELIVERABLES, 1):
        slug = item["slug"]
        cards.append(
            f"""<article class="wyg-card gb spot reveal">
  {_art("what-you-get", slug, WYG_ICONS.get(slug, "file-text"), "wyg-art")}
  <div class="wyg-copy">
    <p class="kicker"><b>{number:02d}</b>{icon(WYG_ICONS.get(slug, "file-text"))}</p>
    <h2>{escape(item["title"])}</h2>
    <p>{escape(item["text"])}</p>
  </div>
</article>"""
        )
    steps = "".join(
        f'<li class="reveal"><span class="n">{n}</span><b>{escape(who)}</b><span>{escape(what)}</span></li>'
        for n, (who, what) in enumerate(FLOW, 1)
    )
    body = page_head(
        "What you get",
        "Your team directs. <em>AI Partner agents</em> do the work.",
        "One engagement replaces the consulting engagement: the research, the panel, the Top 5, and the files your team keeps running after it ends.",
    ) + f"""
<ol class="flow">{steps}</ol>
<div class="wyg-grid">{"".join(cards)}</div>
<section class="cta-band gb spot reveal">
  <div><p class="kicker">Your first engagement is free</p><h2>Describe the problem and watch the panel work.</h2></div>
  <div class="cta-actions"><a class="btn primary" href="/chat">{icon("message-circle")}Start in chat</a><a class="btn ghost" href="/demos">{icon("layers")}See the demos</a></div>
</section>
"""
    return shell("What you get · AI Partner", "/what-you-get", body)

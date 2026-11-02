"""Public catalog and pricing pages."""
from html import escape

from ..catalog import STRATEGY_ARTIFACTS, groups

def _ico(path):
    return (
        '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">'
        f'<path d="{path}"/></svg>'
    )


_CHAT = _ico("M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z")
_DEMOS = _ico("M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5")
_DECK = _ico("M3 4h18v12H3zM8 20h8M12 16v4")
_BOOK = _ico("M2 4h7a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2zM22 4h-7a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h8z")
_PLUG = _ico("M9 7v4M15 7v4M7 11h10v3a5 5 0 0 1-10 0zM12 19v3")
_TAG = _ico("M20 13 11 4H4v7l9 9a2 2 0 0 0 2.8 0L20 15.8a2 2 0 0 0 0-2.8z")
_KEY = _ico("M21 2l-2 2m-2 6a5 5 0 1 1-7-7 5 5 0 0 1 7 7zM15 8l6 6M18 11l3 3")

NAV = f"""
<nav class="links">
  <a href="/chat">{_CHAT} Chat</a>
  <a href="/demos">{_DEMOS} Demos</a>
  <a href="/deck">{_DECK} Deck</a>
  <a href="/catalog">{_BOOK} Catalog</a>
  <a href="/connect">{_PLUG} Connect</a>
  <a href="/pricing">{_TAG} Pricing</a>
  <a class="primary" href="/pricing">{_KEY} Get API key</a>
</nav>
"""

FOOT = """
<footer class="site-foot">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="28" height="28"> AI Partner</a>
  <p>Beta. Billing is not live.</p>
</footer>
"""


def _shell(title, current, body, onboard=False):
    nav = NAV.replace(f'href="{current}"', f'href="{current}" aria-current="page"', 1)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-512.png" sizes="512x512" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/app.css">
</head>
<body>
<div class="bar"><span style="width:100%"></span></div>
<header class="top">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="36" height="36"> AI Partner</a>
  {nav}
</header>
<main class="wrap wide">
{body}
</main>
{FOOT}
{('<script src="/onboard.js"></script>' if onboard else '')}
<script src="/voice.js"></script>
</body>
</html>
"""


def render_catalog():
    blocks = []
    for group in groups():
        cards = []
        for item in group["artifacts"]:
            blob = " ".join([item["title"], item["purpose"], item["group"], item["format"]]).lower()
            sections = ", ".join(escape(name) for name in item["sections"])
            cards.append(
                f"""<article class="deliver" data-artifact="{escape(blob)}">
<h3>{escape(item["title"])}</h3>
<p>{escape(item["purpose"])}</p>
<p class="kicker">{escape(item["format"])} · {sections}</p>
</article>"""
            )
        blocks.append(
            f"""<section>
<h2>{escape(group["task"])}</h2>
<p class="kicker">Thesis draft, Oct 2026. Author's assessment {group["score"]} / 10.</p>
<div class="deliver-grid">{"".join(cards)}</div>
</section>"""
        )
    body = f"""
<p class="kicker">Catalog</p>
<h1>Every artifact a strategy engagement bills for.</h1>
<p class="lede">Nine tasks from the thesis draft, October 2026. Each card is a document this app can write from the job.</p>
<label class="kicker" for="q">Search</label>
<input id="q" type="search" placeholder="Search artifacts">
{"".join(blocks)}
<script>
document.getElementById("q").addEventListener("input", function () {{
  var query = this.value.toLowerCase();
  document.querySelectorAll("[data-artifact]").forEach(function (card) {{
    card.hidden = query && card.getAttribute("data-artifact").indexOf(query) < 0;
  }});
}});
</script>
"""
    return _shell("Catalog · AI Partner", "/catalog", body)


def render_pricing():
    body = f"""
<img class="accent" src="/img/brand/character.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="280" height="210">
<h1>Beta pricing. Billing is not live yet; no card required.</h1>
<div id="onboard-slot"></div>
<div class="plans">
  <article class="plan">
    <h2>Starter</h2>
    <p class="price">Free</p>
    <p>Free beta. 1 strategy engagement.</p>
  </article>
  <article class="plan featured">
    <h2>Strategy</h2>
    <p class="price">$10</p>
    <p>Per engagement. Research brief, market analysis, expert panel, maturity score, Work Chart, harness and skill recommendations, 1 harness kit, 3 skills, and up to {STRATEGY_ARTIFACTS} catalog artifacts.</p>
  </article>
  <article class="plan ink">
    <h2>Harness Build</h2>
    <p class="price">Contact us</p>
    <p>The full catalog, the 10-skill pack, and custom harnesses. <a href="mailto:vivmuk@gmail.com">vivmuk@gmail.com</a></p>
  </article>
</div>
<p><a href="/catalog">See every artifact in the catalog.</a></p>
"""
    return _shell("Pricing · AI Partner", "/pricing", body, onboard=True)

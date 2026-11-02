"""Public catalog and pricing pages."""
from html import escape

from ..catalog import STRATEGY_ARTIFACTS, groups

NAV = """
<nav class="links">
  <a href="/chat">Chat</a>
  <a href="/deck">Deck</a>
  <a href="/catalog">Catalog</a>
  <a href="/connect">Connect</a>
  <a href="/pricing">Pricing</a>
  <a class="primary" href="/pricing">Get API key</a>
</nav>
"""


def _shell(title, current, body):
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
<p class="kicker">Pricing</p>
<img class="accent" src="/img/brand/character.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="280" height="210">
<h1>Beta pricing. Billing is not live yet; no card required.</h1>
<div class="plans">
  <article class="plan">
    <h2>Starter</h2>
    <p class="price">Free</p>
    <p>Free beta. 1 strategy engagement.</p>
  </article>
  <article class="plan">
    <h2>Strategy</h2>
    <p class="price">$10</p>
    <p>Per engagement. Research brief, market analysis, expert panel, maturity score, Work Chart, harness and skill recommendations, 1 harness kit, 3 skills, and up to {STRATEGY_ARTIFACTS} catalog artifacts.</p>
  </article>
  <article class="plan">
    <h2>Harness Build</h2>
    <p class="price">Contact us</p>
    <p>The full catalog, the 10-skill pack, and custom harnesses. <a href="mailto:vivmuk@gmail.com">vivmuk@gmail.com</a></p>
  </article>
</div>
<p><a href="/catalog">See every artifact in the catalog.</a></p>
"""
    return _shell("Pricing · AI Partner", "/pricing", body)

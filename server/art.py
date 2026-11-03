"""The v6 watercolor art for the inner pages: alt text, intrinsic sizes, and one <img> helper."""
import os
from html import escape

STATIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))

WIDE = (1280, 720)
CARD = (1024, 768)

ALT = {
    "img/brand/hero.webp": "A woman with a tablet directs an AI agent while a team of small agents carries charts and notes.",
    "img/catalog/data-gathering-and-market-research.webp": "An AI agent holds up a glowing globe for a man while small agents gather findings in baskets.",
    "img/catalog/benchmarking-and-comps.webp": "A man watches AI agents line up beside glass bars of different heights to compare them.",
    "img/catalog/financial-modeling.webp": "A woman directs AI agents as they arrange a glowing grid of cells across a table.",
    "img/catalog/deck-and-exhibit-production.webp": "A woman reviews slides that AI agents lay out along a studio desk.",
    "img/catalog/synthesis-and-recommendations.webp": "A woman holds the summary page while AI agents hand her their notes.",
    "img/catalog/expert-interviews.webp": "A man in headphones talks with an AI agent while other agents listen in.",
    "img/catalog/org-design-and-change.webp": "A man looks on as AI agents link up into a glowing network.",
    "img/catalog/program-management.webp": "A man holds a clipboard as AI agents walk a line of milestone blocks in order.",
    "img/catalog/political-cover-and-decision-validation.webp": "An AI agent holds a balanced scale for a man while small agents bring notes.",
    "img/what-you-get/research-brief.webp": "An AI agent hands a man a brief while small agents with magnifying glasses check sources.",
    "img/what-you-get/market-analysis.webp": "A woman holds a market map as AI agents bring her charts.",
    "img/what-you-get/expert-panel.webp": "A man takes notes at a round table while a panel of AI agents presents.",
    "img/what-you-get/maturity-score.webp": "A man watches an AI agent set the needle on a large maturity gauge.",
    "img/what-you-get/work-chart.webp": "Two people at the top of a work chart direct the AI agents arranged below them.",
    "img/what-you-get/harness-recommendations.webp": "An AI agent points out plans on a board to a man while other agents watch.",
    "img/what-you-get/harness-kit.webp": "A man fits glowing hexagon pieces together with an AI agent over an open toolkit case.",
    "img/what-you-get/skill-pack.webp": "A man picks a colored tile from a tray that AI agents hold out to him.",
    "img/what-you-get/mcp-api-access.webp": "A man on a laptop connects through a glowing hub to many AI agents.",
    "demos/img/maritime-cover.webp": "A cargo ship at sea with AI agents working the containers on deck and one person directing them from the bridge.",
    "demos/img/maritime-market.webp": "A man and an AI agent mark up a nautical chart while small agents measure routes across it.",
    "demos/img/maritime-panel.webp": "A seated man listens to a panel of AI agents in a room that looks out on a harbor.",
    "demos/img/maritime-build.webp": "A man with a tablet directs AI agents as a crane arm stacks container blocks on a dock.",
    "demos/img/keiki-cover.webp": "A man stands in an open beachside room with tropical flowers, surrounded by AI agents.",
    "demos/img/keiki-market.webp": "A woman leans over a map table with plumeria while AI agents point out areas to her.",
    "demos/img/keiki-panel.webp": "Two people sit at a round table under monstera leaves while a panel of AI agents debates.",
    "demos/img/keiki-build.webp": "A man with a tablet directs AI agents as they assemble glowing pieces.",
    "demos/img/orchid-cover.webp": "A man stands in a ring of AI agents framed by blue orchids.",
    "demos/img/orchid-market.webp": "A woman reviews cards that AI agents lay out on a table among blue orchids.",
    "demos/img/orchid-panel.webp": "A man watches a panel of AI agents, each holding up a glowing idea, framed by blue orchids.",
    "demos/img/orchid-build.webp": "A man on a laptop directs AI agents carrying glowing panels among blue orchids.",
}


def size(path):
    return WIDE if path.startswith(("img/catalog/", "deck/img/")) else CARD


def exists(path):
    return os.path.isfile(os.path.join(STATIC, path))


def img(path, cls="", eager=False):
    """An <img> with intrinsic width and height (no layout shift), alt text, and lazy loading below the fold."""
    width, height = size(path)
    attrs = [
        f'src="/{escape(path)}"',
        f'alt="{escape(ALT.get(path, ""))}"',
        f'width="{width}"',
        f'height="{height}"',
        'decoding="async"',
        'fetchpriority="high"' if eager else 'loading="lazy"',
    ]
    if cls:
        attrs.insert(0, f'class="{escape(cls)}"')
    return "<img " + " ".join(attrs) + ">"

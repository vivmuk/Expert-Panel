DELIVERABLES = (
    {
        "slug": "research-brief",
        "title": "Cited research brief",
        "text": "A short brief that keeps every source URL the search returned.",
        "alt": "A robot on a library ladder ties books on the shelves to a brief on the table.",
    },
    {
        "slug": "market-analysis",
        "title": "Market analysis",
        "text": "Search queries on the industry, competitors, benchmarks, and regulations, and the pages those queries returned.",
        "alt": "Three robots study a tabletop map of hills, a river, flags, and a bar chart.",
    },
    {
        "slug": "expert-panel",
        "title": "Expert panel of strategy agents",
        "text": "Four personas, a consensus, the dissent, and now, next, and later. Say red team to add the attack.",
        "alt": "Robots in different hats sit around a table under one shared lightbulb.",
    },
    {
        "slug": "maturity-score",
        "title": "AI maturity score 1–4",
        "text": "A score from 1 to 4: Invoice-led, Pilot-led, Hybrid, or Machine-led.",
        "alt": "A small robot climbs four stone steps, from a sprout to a flowering tree.",
    },
    {
        "slug": "work-chart",
        "title": "Work Chart",
        "text": "Today, with every step Human, and the agent era, with Human, AI Agent, or Hybrid on each step.",
        "alt": "A person and cargo carts meet a robot directing smaller robots on branching tracks.",
    },
    {
        "slug": "harness-recommendations",
        "title": "Harness and skill recommendations",
        "text": "The chart names the steps an agent can take, and the pack names the skills that cover them.",
        "alt": "A robot measures cloth for three people beside a framed drawing of a harness.",
    },
    {
        "slug": "harness-kit",
        "title": "Harness kit (1 harness)",
        "text": "One zip: CLAUDE.md, playbook.md, model-routing.md, project-state-schema.md, and skills/.",
        "alt": "An open suitcase holds tools, gears, and a robot, with two small robots beside it.",
    },
    {
        "slug": "skill-pack",
        "title": "Skill pack (3 skills)",
        "text": "A zip of up to 3 skills. Each one has SKILL.md, references/research.md, scripts/render.py, and templates.",
        "alt": "A robot stands by a shelf of three jars holding gears, a quill, and a compass.",
    },
    {
        "slug": "mcp-api-access",
        "title": "Use it from ChatGPT, Claude, Cursor",
        "text": "A streamable MCP server at /mcp and an OpenAI-compatible API at /v1/chat/completions.",
        "alt": "A robot plugs blue cables into a switchboard with a cursor and a speech bubble.",
    },
)

LANDING = ("research-brief", "expert-panel", "work-chart", "harness-kit")


def by_slug(slug):
    for item in DELIVERABLES:
        if item["slug"] == slug:
            return item
    raise KeyError(slug)

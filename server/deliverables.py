DELIVERABLES = (
    {
        "slug": "research-brief",
        "title": "Cited research brief",
        "text": "A short brief that keeps every source URL the search returned.",
    },
    {
        "slug": "market-analysis",
        "title": "Market analysis",
        "text": "Search queries on the industry, competitors, benchmarks, and regulations, and the pages those queries returned.",
    },
    {
        "slug": "expert-panel",
        "title": "Panel of 20 AI experts",
        "text": "Twenty AI-generated experts, each with a distinct lens, debate the job over two rounds before a judge ranks the Top 5.",
    },
    {
        "slug": "maturity-score",
        "title": "AI maturity score 1–4",
        "text": "A score from 1 to 4: Invoice-led, Pilot-led, Hybrid, or Machine-led.",
    },
    {
        "slug": "work-chart",
        "title": "Work Chart",
        "text": "Today, with every step Human, and the agent era, with Human, AI Agent, or Hybrid on each step.",
    },
    {
        "slug": "harness-recommendations",
        "title": "Harness and skill recommendations",
        "text": "The chart names the steps an agent can take, and the pack names the skills that cover them.",
    },
    {
        "slug": "harness-kit",
        "title": "Harness kit (1 harness)",
        "text": "One zip: CLAUDE.md, playbook.md, model-routing.md, project-state-schema.md, and skills/.",
    },
    {
        "slug": "skill-pack",
        "title": "Skill pack (3 skills)",
        "text": "A zip of up to 3 skills. Each one has SKILL.md, references/research.md, scripts/render.py, and templates.",
    },
    {
        "slug": "mcp-api-access",
        "title": "Use it from ChatGPT, Claude, Cursor",
        "text": "A streamable MCP server at /mcp and an OpenAI-compatible API at /v1/chat/completions.",
    },
)


def by_slug(slug):
    for item in DELIVERABLES:
        if item["slug"] == slug:
            return item
    raise KeyError(slug)

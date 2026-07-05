"""Stage 4: real market intelligence via Venice web/X search and URL scraping."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prompts.loader import render
from ..venice.models import get_catalog

logger = logging.getLogger(__name__)

RESEARCH_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "question": {"type": "string"},
                    "why": {"type": "string"},
                    "channel": {"type": "string", "enum": ["web", "x"]},
                },
                "required": ["title", "question", "why", "channel"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["topics"],
    "additionalProperties": False,
}


def scrape_context(client, urls):
    """Fetch client-provided URLs into context documents. Failures are logged
    and skipped so one bad URL never blocks a run."""
    docs = []
    for url in (urls or [])[:5]:
        try:
            result = client.scrape(url)
            content = result.get("content") or result.get("markdown") or str(result)
            docs.append(f"### Scraped: {url}\n{content[:8000]}")
        except Exception:
            logger.exception("Scrape failed for %s", url)
    return docs


def gather_market_intelligence(
    client,
    planner_model,
    search_model,
    problem,
    *,
    topic_count=5,
    enable_x=False,
    concurrency=4,
    ledger=None,
    on_completed=None,
    on_planned=None,
):
    plan_prompt = render("panel/market_query_planner", topic_count=topic_count, problem=problem)
    plan = client.structured(
        planner_model,
        [{"role": "user", "content": plan_prompt}],
        "ResearchPlan",
        RESEARCH_PLAN_SCHEMA,
        ledger=ledger,
        stage="market",
    )
    topics = plan.get("topics", [])[:topic_count]
    if on_planned:
        on_planned([{"title": t.get("title"), "channel": t.get("channel", "web"), "why": t.get("why")} for t in topics])

    x_capable = bool(get_catalog().capabilities(search_model).get("supportsXSearch"))

    def research(topic):
        use_x = enable_x and x_capable and topic.get("channel") == "x"
        prompt = render("panel/market_agent", problem=problem, question=topic["question"])
        result = client.chat_search(
            search_model,
            [{"role": "user", "content": prompt}],
            web="on",
            citations=True,
            x_search=use_x,
            ledger=ledger,
            stage="market",
        )
        citations = []
        for i, r in enumerate(result["search_results"], start=1):
            if isinstance(r, dict):
                citations.append(
                    {"index": i, "url": r.get("url", ""), "title": r.get("title", r.get("url", ""))}
                )
        return {
            "topic": topic["title"],
            "question": topic["question"],
            "channel": "x" if use_x else "web",
            "findings": result["content"],
            "citations": citations,
        }

    briefs = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(research, t): t for t in topics}
        for fut in as_completed(futures):
            topic = futures[fut]
            try:
                brief = fut.result()
            except Exception as exc:
                logger.exception("Market research failed for topic %s", topic.get("title"))
                brief = {
                    "topic": topic.get("title", "unknown"),
                    "question": topic.get("question", ""),
                    "channel": topic.get("channel", "web"),
                    "findings": f"Research unavailable: {exc}",
                    "citations": [],
                }
            briefs.append(brief)
            if on_completed:
                on_completed(brief)
    return briefs


def digest(briefs, limit=600):
    """Short digest of market briefs to prime the experts without blowing context."""
    parts = []
    for b in briefs:
        parts.append(f"- {b['topic']}: {b['findings'][:limit]}")
    return "\n".join(parts)

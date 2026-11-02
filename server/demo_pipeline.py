"""Full-depth demo run: 20 experts, two debate rounds, a judge, and Exa citations only."""
from concurrent.futures import ThreadPoolExecutor

from .catalog import by_id, recommend
from .demo_schema import LEVELS, empty_demo, keep_citations, level
from .skillpack import _slug, agent_steps, plan_slots

EXPERTS = 20
ROUNDS = 2
WAVE = 5

_QUERY_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 4}},
    "required": ["queries"],
    "additionalProperties": False,
}
_MARKET_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}, "note": {"type": "string"}},
                "required": ["title", "url", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "citations"],
    "additionalProperties": False,
}
_EXPERT_SCHEMA = {
    "type": "object",
    "properties": {
        "experts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "background": {"type": "string"},
                    "lens": {"type": "string"},
                },
                "required": ["name", "role", "background", "lens"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["experts"],
    "additionalProperties": False,
}
_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "risks": {"type": "string"},
        "opportunities": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["risks", "opportunities", "recommendation"],
    "additionalProperties": False,
}
_DEBATE_SCHEMA = {
    "type": "object",
    "properties": {"statement": {"type": "string"}, "responding_to": {"type": "string"}},
    "required": ["statement", "responding_to"],
    "additionalProperties": False,
}
_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "citation_url": {"type": "string"},
                    "backers": {"type": "array", "items": {"type": "string"}},
                    "dissenters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "why": {"type": "string"}},
                            "required": ["name", "why"],
                            "additionalProperties": False,
                        },
                    },
                    "confidence": {"type": "string", "enum": list(LEVELS)},
                    "impact": {"type": "string", "enum": list(LEVELS)},
                    "effort": {"type": "string", "enum": list(LEVELS)},
                },
                "required": ["title", "detail", "citation_url", "backers", "dissenters", "confidence", "impact", "effort"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False,
}
_CHART_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "current": {"type": "array", "items": {"type": "object", "properties": {"step": {"type": "string"}, "task": {"type": "string"}, "owner": {"type": "string"}}, "required": ["step", "task", "owner"], "additionalProperties": False}},
        "future": {"type": "array", "items": {"type": "object", "properties": {"step": {"type": "string"}, "task": {"type": "string"}, "owner": {"type": "string"}}, "required": ["step", "task", "owner"], "additionalProperties": False}},
    },
    "required": ["summary", "current", "future"],
    "additionalProperties": False,
}
_MATURITY_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
    "additionalProperties": False,
}


def run_demo(slug, problem, complete, search):
    demo = empty_demo(slug, problem)
    queries = _queries(problem, complete)
    hits = []
    allowed = set()
    for query in queries:
        for hit in search(query, limit=4) or []:
            url = (hit or {}).get("url") or ""
            if not url or url in allowed:
                continue
            allowed.add(url)
            hits.append(hit)
    summary = _market_summary(problem, hits, complete)
    demo["market"] = {"summary": summary.get("summary") or "", "citations": keep_citations(summary.get("citations"), allowed)}
    if not demo["market"]["citations"]:
        demo["market"]["citations"] = keep_citations(hits, allowed)
    experts = _experts(problem, demo["market"]["summary"], complete)
    _feedback(problem, experts, complete)
    debate = []
    for round_no in (1, 2):
        debate.extend(_debate(problem, experts, debate, round_no, complete))
    demo["experts"] = experts
    demo["debate"] = debate
    demo["top5"] = _top5(problem, experts, debate, allowed, complete)
    demo["maturity"] = _maturity(problem, complete)
    demo["chart"] = _chart(problem, complete)
    demo["skills"] = _skills(demo["chart"])
    demo["artifacts"] = [
        {"id": artifact_id, "title": (by_id(artifact_id) or {}).get("title") or artifact_id}
        for artifact_id in recommend({"problem": problem})
    ]
    demo["generated"] = True
    return demo


def _queries(problem, complete):
    data = complete(
        "ChatDemoQueries",
        [{"role": "user", "content": "Write 3 or 4 web search queries for this public-information brief.\n\n" + problem}],
        _QUERY_SCHEMA,
        400,
    )
    found = []
    for item in (data or {}).get("queries") or []:
        text = " ".join(str(item).split())
        if text and text not in found:
            found.append(text[:180])
    return found[:4] or [problem.split("\n", 1)[0][:180]]


def _market_summary(problem, hits, complete):
    lines = []
    for hit in hits:
        lines.append(f"{hit.get('title')}\n{hit.get('url')}\n{hit.get('content')}")
    data = complete(
        "ChatDemoMarket",
        [{
            "role": "user",
            "content": (
                "Write a short market note. Cite only the URLs listed below. "
                "If a number is not in those pages, write assumption next to it. Do not invent sources.\n\n"
                + problem
                + "\n\nSources:\n"
                + "\n\n".join(lines)
            ),
        }],
        _MARKET_SCHEMA,
        900,
    )
    return data or {}


def _experts(problem, market, complete):
    experts = []
    for _ in range(4):
        need = min(WAVE, EXPERTS - len(experts))
        if need <= 0:
            break
        names = ", ".join(item["name"] for item in experts) or "none"
        data = complete(
            "ChatDemoExperts",
            [{
                "role": "user",
                "content": (
                    f"Create {need} AI-generated experts for this job. They are not real people. "
                    f"Do not repeat these names: {names}.\n\n{problem}\n\n{market[:1500]}"
                ),
            }],
            _EXPERT_SCHEMA,
            1200,
        )
        for item in (data or {}).get("experts") or []:
            name = " ".join(str(item.get("name") or "").split())
            if not name or any(existing["name"] == name for existing in experts):
                continue
            experts.append(
                {
                    "name": name[:80],
                    "role": str(item.get("role") or "")[:80],
                    "background": str(item.get("background") or "")[:400],
                    "lens": str(item.get("lens") or "")[:200],
                    "badge": "AI-generated expert",
                    "risks": "",
                    "opportunities": "",
                    "recommendation": "",
                }
            )
            if len(experts) >= EXPERTS:
                break
    return experts[:EXPERTS]


def _feedback(problem, experts, complete):
    def one(expert):
        data = complete(
            "ChatDemoFeedback",
            [{
                "role": "user",
                "content": (
                    f"You are {expert['name']}, {expert['role']}. {expert['background']} Lens: {expert['lens']}. "
                    "Give risks, opportunities, and one recommendation. Do not invent statistics.\n\n" + problem
                ),
            }],
            _FEEDBACK_SCHEMA,
            500,
        ) or {}
        expert["risks"] = str(data.get("risks") or "")[:400]
        expert["opportunities"] = str(data.get("opportunities") or "")[:400]
        expert["recommendation"] = str(data.get("recommendation") or "")[:400]

    _map(experts, one)


def _debate(problem, experts, prior, round_no, complete):
    transcript = "\n".join(f"{item['name']}: {item['statement']}" for item in prior[-20:])

    def one(expert):
        data = complete(
            "ChatDemoDebate",
            [{
                "role": "user",
                "content": (
                    f"Round {round_no}. You are {expert['name']}, {expert['role']}. "
                    "Respond to another expert. Do not invent statistics.\n\n"
                    + (transcript or "No earlier remarks.")
                    + "\n\n" + problem
                ),
            }],
            _DEBATE_SCHEMA,
            400,
        ) or {}
        return {
            "round": round_no,
            "name": expert["name"],
            "statement": str(data.get("statement") or "")[:500],
            "responding_to": str(data.get("responding_to") or "")[:80],
        }

    return [item for item in _map(experts, one) if item["statement"]]


def _top5(problem, experts, debate, allowed, complete):
    names = ", ".join(item["name"] for item in experts)
    urls = "\n".join(sorted(allowed))
    data = complete(
        "ChatDemoJudge",
        [{
            "role": "user",
            "content": (
                "Pick the top 5 recommendations. Each citation_url must be one of the URLs listed, or empty. "
                "Rate confidence, impact, and effort as high, medium, or low. "
                "Name backers and dissenters only from this roster: "
                + names
                + "\n\nURLs:\n" + urls
                + "\n\n" + problem
            ),
        }],
        _JUDGE_SCHEMA,
        1200,
    ) or {}
    found = []
    for item in (data.get("recommendations") or [])[:5]:
        url = item.get("citation_url") or ""
        if url not in allowed:
            url = ""
        found.append(
            {
                "title": str(item.get("title") or "")[:140],
                "detail": str(item.get("detail") or "")[:400],
                "citation_url": url,
                "backers": [str(name)[:80] for name in (item.get("backers") or [])[:6]],
                "dissenters": [
                    {"name": str(row.get("name") or "")[:80], "why": str(row.get("why") or "")[:200]}
                    for row in (item.get("dissenters") or [])[:4]
                    if isinstance(row, dict)
                ],
                "confidence": level(item.get("confidence")),
                "impact": level(item.get("impact")),
                "effort": level(item.get("effort")),
            }
        )
    return found


def _maturity(problem, complete):
    data = complete(
        "ChatDemoMaturity",
        [{"role": "user", "content": "Score AI maturity from 1 to 4 for the team in this brief. 1 is Invoice-led, 2 Pilot-led, 3 Hybrid, 4 Machine-led.\n\n" + problem}],
        _MATURITY_SCHEMA,
        300,
    ) or {}
    score = data.get("score")
    if score not in (1, 2, 3, 4):
        score = 2
    return {"score": score, "reason": str(data.get("reason") or "")[:300]}


def _chart(problem, complete):
    data = complete(
        "ChatDemoChart",
        [{"role": "user", "content": "Map the work today (owner Human) and in the agent era (Human, AI Agent, or Hybrid). 3 to 6 steps each.\n\n" + problem}],
        _CHART_SCHEMA,
        900,
    ) or {}
    if not data.get("current") or not data.get("future"):
        return None
    return data


def _skills(chart):
    """One entry per skill folder the full-depth kit would hold. No padding."""
    if not chart:
        return []
    used = set()
    found = []
    for slot in plan_slots("large", agent_steps(chart)):
        if slot["level"] == "orchestrator":
            name = _slug("run the engagement", used)
            purpose = "Run the agent-era process end to end and call the workflow skills in order."
        else:
            name = _slug(slot["step"]["step"], used)
            purpose = f"{slot['step']['owner']}. {slot['step']['task']}"
        found.append(
            {
                "name": name,
                "purpose": purpose[:300],
                "files": [f"skills/{name}/SKILL.md", f"skills/{name}/references/research.md", f"skills/{name}/scripts/render.py"],
            }
        )
    return found


def _map(items, fn):
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=WAVE) as pool:
        return list(pool.map(fn, items))

"""Full-depth demo run: 20 experts, two debate rounds, a judge, and Exa citations only."""
from concurrent.futures import ThreadPoolExecutor

from .catalog import recommend
from .demo_schema import empty_demo, keep_citations, level
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
_LMH = {"type": "string", "enum": ["High", "Medium", "Low"]}
_STRS = {"type": "array", "items": {"type": "string"}}
_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "risks": {"type": "string"},
        "opportunities": {"type": "string"},
        "recommendation": {"type": "string"},
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "insight": {"type": "string"},
                    "supporting_reasoning": {"type": "string"},
                    "confidence_level": _LMH,
                    "implementation_ideas": _STRS,
                    "identified_risks": _STRS,
                    "identified_opportunities": _STRS,
                },
                "required": ["insight", "supporting_reasoning", "confidence_level", "implementation_ideas", "identified_risks", "identified_opportunities"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["risks", "opportunities", "recommendation", "insights"],
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
                    "confidence": _LMH,
                    "impact": _LMH,
                    "effort": _LMH,
                    "rationale": {"type": "string"},
                    "risks": _STRS,
                    "metrics": _STRS,
                    "next_steps": _STRS,
                },
                "required": ["title", "detail", "citation_url", "backers", "dissenters", "confidence", "impact", "effort", "rationale", "risks", "metrics", "next_steps"],
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
_SYNTH_SCHEMA = {
    "type": "object",
    "properties": {
        "cohesive_summary": {"type": "string"},
        "key_themes": _STRS,
        "potential_blind_spots": _STRS,
        "actionable_next_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"step_description": {"type": "string"}, "priority": _LMH, "suggested_rationale": {"type": "string"}},
                "required": ["step_description", "priority", "suggested_rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cohesive_summary", "key_themes", "potential_blind_spots", "actionable_next_steps"],
    "additionalProperties": False,
}
_SKILLS_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "instructions": {"type": "string"},
                    "helper_filename": {"type": "string"},
                    "helper_content": {"type": "string"},
                },
                "required": ["name", "description", "instructions", "helper_filename", "helper_content"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["skills"],
    "additionalProperties": False,
}
_HARNESS_SCHEMA = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
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
        try:
            found = search(query, limit=4) or []
        except Exception:  # one slow query should not sink the run
            found = []
        for hit in found:
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
    demo["synthesis"] = _synthesis(problem, experts, debate, complete)
    demo["top5"] = _top5(problem, experts, debate, allowed, complete)
    demo["maturity"] = _maturity(problem, complete)
    demo["chart"] = _chart(problem, complete)
    kit_skills = _kit_skills(problem, demo, complete)
    demo["kit_files"] = {"skills": kit_skills, "harness": _harness(problem, demo, kit_skills, complete)}
    demo["skills"] = [item["name"] for item in kit_skills] or _skills(demo["chart"])
    demo["artifacts"] = [{"id": artifact_id, "title": artifact_id} for artifact_id in recommend({"problem": problem})]
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
                    "Analyze the problem strictly from your perspective. Give risks, opportunities, one recommendation, "
                    "and 2 or 3 insights. Each insight needs detailed supporting reasoning, a confidence level, exactly 3 "
                    "specific implementation ideas, and its risks and opportunities. Do not invent statistics, customers, or quotes.\n\n" + problem
                ),
            }],
            _FEEDBACK_SCHEMA,
            2500,
        ) or {}
        expert["insights"] = [
            {
                "insight": str(row.get("insight") or "")[:400],
                "supporting_reasoning": str(row.get("supporting_reasoning") or "")[:900],
                "confidence_level": str(row.get("confidence_level") or "")[:10],
                "implementation_ideas": [str(x)[:300] for x in (row.get("implementation_ideas") or [])[:3]],
                "identified_risks": [str(x)[:240] for x in (row.get("identified_risks") or [])[:4]],
                "identified_opportunities": [str(x)[:240] for x in (row.get("identified_opportunities") or [])[:4]],
            }
            for row in (data.get("insights") or [])[:3]
            if isinstance(row, dict) and row.get("insight")
        ]
        expert["risks"] = str(data.get("risks") or "")[:600]
        expert["opportunities"] = str(data.get("opportunities") or "")[:600]
        expert["recommendation"] = str(data.get("recommendation") or "")[:600]

    _map(experts, one)


def _debate(problem, experts, prior, round_no, complete):
    transcript = "\n".join(f"{item['name']}: {item['statement']}" for item in prior[-20:])
    if not prior:
        transcript = "\n".join(f"{item['name']} ({item['role']}): {item['recommendation']}" for item in experts)

    def one(expert):
        data = complete(
            "ChatDemoDebate",
            [{
                "role": "user",
                "content": (
                    f"Round {round_no}. You are {expert['name']}, {expert['role']}. "
                    "Respond to one named expert below: agree or challenge with specific reasoning. Put that expert's name in responding_to. "
                    "Do not invent statistics.\n\n"
                    + (transcript or "No earlier remarks.")
                    + "\n\n" + problem
                ),
            }],
            _DEBATE_SCHEMA,
            900,
        ) or {}
        return {
            "round": round_no,
            "name": expert["name"],
            "statement": str(data.get("statement") or "")[:900],
            "responding_to": str(data.get("responding_to") or "")[:80],
        }

    return [item for item in _map(experts, one) if item["statement"]]


def _top5(problem, experts, debate, allowed, complete):
    names = ", ".join(item["name"] for item in experts)
    urls = "\n".join(sorted(allowed))
    views = "\n".join(f"{item['name']} ({item['role']}): {item['recommendation']}" for item in experts)
    talk = "\n".join(f"R{item['round']} {item['name']} -> {item['responding_to']}: {item['statement'][:400]}" for item in debate)
    data = complete(
        "ChatDemoJudge",
        [{
            "role": "user",
            "content": (
                "You are the judge. Pick exactly 5 recommendations from the panel and debate. For each give a detail paragraph, "
                "rationale tied to the debate, confidence, impact, effort, 2-3 risks, 2-3 success metrics to track (no invented baselines), "
                "and 3 next steps. Each citation_url must be one of the URLs listed, or empty. "
                "Name backers and dissenters only from this roster: "
                + names
                + "\n\nExpert recommendations:\n" + views
                + "\n\nDebate:\n" + talk[:12000]
                + "\n\nURLs:\n" + urls
                + "\n\n" + problem
            ),
        }],
        _JUDGE_SCHEMA,
        6000,
    ) or {}
    found = []
    for item in (data.get("recommendations") or [])[:5]:
        url = item.get("citation_url") or ""
        if url not in allowed:
            url = ""
        found.append(
            {
                "title": str(item.get("title") or "")[:140],
                "detail": str(item.get("detail") or "")[:900],
                "rationale": str(item.get("rationale") or "")[:700],
                "risks": [str(x)[:240] for x in (item.get("risks") or [])[:3]],
                "metrics": [str(x)[:240] for x in (item.get("metrics") or [])[:3]],
                "next_steps": [str(x)[:240] for x in (item.get("next_steps") or [])[:3]],
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


def _synthesis(problem, experts, debate, complete):
    views = "\n".join(f"{item['name']} ({item['role']}): {item['recommendation']} Risks: {item['risks'][:200]}" for item in experts)
    talk = "\n".join(f"{item['name']}: {item['statement'][:300]}" for item in debate)
    data = complete(
        "ChatDemoSynthesis",
        [{"role": "user", "content": (
            "You are a Chief Synthesis Officer. From the expert views and debate, write a cohesive summary (2-3 sentences), "
            "2-4 key themes, 1-3 potential blind spots or conflicts, and 3-5 actionable next steps with priority and rationale. "
            "Do not invent statistics.\n\n" + problem + "\n\nExperts:\n" + views + "\n\nDebate:\n" + talk[:10000]
        )}],
        _SYNTH_SCHEMA,
        3000,
    ) or {}
    if not data.get("cohesive_summary"):
        return None
    return data


def _brief(problem, demo):
    tops = "\n".join(f"- {t['title']}: {t['detail'][:300]}" for t in demo.get("top5") or [])
    future = "\n".join(f"- {s.get('step')} ({s.get('owner')}): {s.get('task')}" for s in ((demo.get("chart") or {}).get("future") or []))
    return problem + "\n\nTop 5:\n" + tops + "\n\nAgent-era work chart:\n" + future


def _kit_skills(problem, demo, complete):
    data = complete(
        "ChatDemoSkills",
        [{"role": "user", "content": (
            "Write exactly 3 Claude Agent Skills that implement the top recommendations for this company. Follow Anthropic's skill format: "
            "name is lowercase-hyphenated (max 64 chars); description says what the skill does AND when Claude should use it (one or two sentences); "
            "instructions is the SKILL.md markdown body with sections: Overview, When to use, Inputs, Steps (numbered), Output format, Guardrails, Example. "
            "helper_filename is one supporting file (e.g. checklist.md, template.md or schema.json) and helper_content its full content, referenced from the instructions. "
            "Use only public information; do not invent customers, metrics or quotes.\n\n" + _brief(problem, demo)
        )}],
        _SKILLS_SCHEMA,
        7000,
    ) or {}
    found = []
    for row in (data.get("skills") or [])[:3]:
        name = "".join(ch if ch.isalnum() else "-" for ch in str(row.get("name") or "").lower()).strip("-")[:64]
        helper = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(row.get("helper_filename") or ""))[:60]
        if not name or not row.get("instructions"):
            continue
        found.append({
            "name": name,
            "description": " ".join(str(row.get("description") or "").split())[:1000],
            "instructions": str(row.get("instructions") or ""),
            "helper_filename": helper if helper and helper != "SKILL.md" else "",
            "helper_content": str(row.get("helper_content") or ""),
        })
    return found


def _harness(problem, demo, skills, complete):
    names = ", ".join(item["name"] for item in skills)
    data = complete(
        "ChatDemoHarness",
        [{"role": "user", "content": (
            "Return only the markdown document, no preamble. Write a harness design document for an agent harness that delivers the Top 5 for this company. "
            "Use these sections with ## headings: Purpose, Architecture (include a mermaid flowchart), Agents and roles (table), "
            "Tools and MCP servers, Skills (use these: " + names + "), State schema, Workflow, Guardrails and anti-patterns, "
            "Evals (offline and online, with pass criteria), QHX improvement loop (every production run writes one delta to the anti-pattern list), "
            "Rollout plan (30/60/90 days). Label targets as targets, not results. Do not invent customers, metrics or quotes.\n\n"
            + _brief(problem, demo)
        )}],
        None,
        8000,
    ) or {}
    return str(data.get("markdown") or "") or None


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

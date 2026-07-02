"""Stage 5: synthesis. Single streamed call for panels ≤30; map-reduce
(theme clustering → parallel theme summaries → final reduce) above that."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prompts.loader import render

logger = logging.getLogger(__name__)

HIERARCHICAL_THRESHOLD = 30

SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "key_themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "evidence": {"type": "string"},
                    "driving_experts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["theme", "evidence", "driving_experts"],
                "additionalProperties": False,
            },
        },
        "consensus_dissent": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "type": {"type": "string", "enum": ["consensus", "dissent"]},
                    "summary": {"type": "string"},
                },
                "required": ["topic", "type", "summary"],
                "additionalProperties": False,
            },
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "string"},
                    "horizon": {"type": "string", "enum": ["Now", "Next", "Later"]},
                    "rationale": {"type": "string"},
                    "first_step": {"type": "string"},
                    "success_measure": {"type": "string"},
                },
                "required": ["recommendation", "horizon", "rationale", "first_step", "success_measure"],
                "additionalProperties": False,
            },
        },
        "risks_and_blind_spots": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "executive_summary",
        "key_themes",
        "consensus_dissent",
        "recommendations",
        "risks_and_blind_spots",
        "next_steps",
    ],
    "additionalProperties": False,
}

CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "insight_indices": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["name", "description", "insight_indices"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["themes"],
    "additionalProperties": False,
}


def _insight_lines(insight_entries):
    lines = []
    for entry in insight_entries:
        persona = entry.get("persona", {})
        who = f"{persona.get('name', '?')} ({persona.get('title', '')}, {persona.get('discipline', '')})"
        for item in entry.get("insights_and_analysis", []):
            lines.append(
                {
                    "who": who,
                    "text": f"{item.get('insight', '')} — {item.get('supporting_reasoning', '')[:400]} "
                    f"[confidence: {item.get('confidence_level', '?')}]",
                }
            )
    return lines


def _market_block(market_briefs):
    parts = []
    for b in market_briefs or []:
        cites = " ".join(f"^{c['index']}^ {c['url']}" for c in b.get("citations", [])[:8])
        parts.append(f"### {b['topic']}\n{b['findings']}\nSources: {cites or 'none returned'}")
    return "\n\n".join(parts) or "No market intelligence available."


def synthesize(client, model, problem, insight_entries, market_briefs, panel_size, ledger):
    lines = _insight_lines(insight_entries)
    market_block = _market_block(market_briefs)

    if len(lines) <= HIERARCHICAL_THRESHOLD * 2 and panel_size <= HIERARCHICAL_THRESHOLD:
        insights_block = "\n".join(f"- [{l['who']}] {l['text']}" for l in lines)
    else:
        insights_block = _hierarchical_digest(client, model, problem, lines, ledger)

    prompt = render(
        "panel/synthesis",
        panel_size=panel_size,
        problem=problem,
        insights_block=insights_block[:80000],
        market_block=market_block[:30000],
    )
    return client.structured(
        model,
        [{"role": "user", "content": prompt}],
        "SynthesisReport",
        SYNTHESIS_SCHEMA,
        max_completion_tokens=8000,
        ledger=ledger,
        stage="synthesis",
    )


def _hierarchical_digest(client, model, problem, lines, ledger):
    """Cluster indexed insights into themes, summarize each theme in parallel,
    and hand the theme summaries to the final synthesis call."""
    indexed = "\n".join(f"{i}. [{l['who']}] {l['text'][:300]}" for i, l in enumerate(lines))
    clusters = client.structured(
        model,
        [{"role": "user", "content": render("panel/synthesis_cluster", problem=problem, insights_block=indexed[:60000])}],
        "InsightClusters",
        CLUSTER_SCHEMA,
        ledger=ledger,
        stage="synthesis",
    )

    def summarize(theme):
        members = [lines[i] for i in theme.get("insight_indices", []) if 0 <= i < len(lines)]
        block = "\n".join(f"- [{m['who']}] {m['text']}" for m in members)
        deltas = client.chat_stream(
            model,
            [
                {
                    "role": "user",
                    "content": render(
                        "panel/synthesis_theme",
                        problem=problem,
                        theme_name=theme["name"],
                        theme_description=theme["description"],
                        insights_block=block[:40000],
                    ),
                }
            ],
            max_completion_tokens=1500,
            on_usage=lambda u: ledger and ledger.record("synthesis", model, u),
        )
        return theme["name"], "".join(deltas)

    summaries = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(summarize, t) for t in clusters.get("themes", [])]
        for fut in as_completed(futures):
            try:
                name, text = fut.result()
                summaries.append(f"### Theme: {name}\n{text}")
            except Exception:
                logger.exception("Theme summary failed")
    return "\n\n".join(summaries)

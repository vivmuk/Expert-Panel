"""Stage 3: every persona analyzes the problem, in parallel with bounded concurrency."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prompts.loader import render

logger = logging.getLogger(__name__)

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "insights_and_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "insight": {"type": "string"},
                    "supporting_reasoning": {"type": "string"},
                    "confidence_level": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "implementation_ideas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "identified_risks": {"type": "array", "items": {"type": "string"}},
                    "identified_opportunities": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "insight",
                    "supporting_reasoning",
                    "confidence_level",
                    "implementation_ideas",
                    "identified_risks",
                    "identified_opportunities",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["insights_and_analysis"],
    "additionalProperties": False,
}


def collect_insights(
    client,
    model,
    problem,
    personas,
    concurrency,
    ledger,
    market_digest=None,
    prompt_name="panel/expert_insight",
    schema=None,
    on_started=None,
    on_completed=None,
    cancel_event=None,
):
    schema = schema or INSIGHT_SCHEMA
    market_context = ""
    if market_digest:
        market_context = f"## Market intelligence summary (from live research)\n{market_digest[:4000]}"

    def ask(index, persona):
        if cancel_event is not None and cancel_event.is_set():
            return index, persona, None
        if on_started:
            on_started(index, persona)
        prompt = render(
            prompt_name,
            name=persona["name"],
            title=persona.get("title", ""),
            background=persona.get("background", ""),
            focus_areas=", ".join(persona.get("focus_areas") or []),
            perspective=persona.get("perspective", ""),
            problem=problem,
            market_context=market_context,
        )
        result = client.structured(
            model,
            [{"role": "user", "content": prompt}],
            "ExpertInsight",
            schema,
            ledger=ledger,
            stage="insights",
        )
        return index, persona, result

    insights = [None] * len(personas)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(ask, i, p) for i, p in enumerate(personas)]
        for fut in as_completed(futures):
            try:
                index, persona, result = fut.result()
            except Exception as exc:
                logger.exception("Insight generation failed")
                continue
            entry = {"persona": persona}
            if result is None:
                entry["error"] = "cancelled"
            else:
                entry.update(result)
            insights[index] = entry
            if on_completed:
                on_completed(index, entry)

    # Replace any slots that failed entirely
    return [
        e if e is not None else {"persona": personas[i], "error": "failed", "insights_and_analysis": []}
        for i, e in enumerate(insights)
    ]

"""Stage 1: the Panel Architect designs a coverage blueprint for the panel."""
import logging

from ..prompts.loader import render
from ..venice.client import get_client

logger = logging.getLogger(__name__)

BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "disciplines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                    "rationale": {"type": "string"},
                    "industries": {"type": "array", "items": {"type": "string"}},
                    "seniorityMix": {"type": "string"},
                },
                "required": ["name", "count", "rationale", "industries", "seniorityMix"],
                "additionalProperties": False,
            },
        },
        "mandatedContrarians": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stance": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["stance", "rationale"],
                "additionalProperties": False,
            },
        },
        "coverageNotes": {"type": "string"},
    },
    "required": ["disciplines", "mandatedContrarians", "coverageNotes"],
    "additionalProperties": False,
}


def design_blueprint(client, model, problem, panel_size, guardrails, context_docs, ledger):
    guardrails = guardrails or {}
    context_section = ""
    if context_docs:
        joined = "\n\n".join(context_docs)[:12000]
        context_section = f"## Additional context (scraped from client-provided URLs)\n{joined}"

    prompt = render(
        "panel/architect",
        panel_size=panel_size,
        problem=problem,
        context_section=context_section,
        pinned_experts=", ".join(guardrails.get("pinnedExperts") or []) or "none",
        excluded_domains=", ".join(guardrails.get("excludedDomains") or []) or "none",
        seed_perspectives=guardrails.get("seedPerspectives") or "none specified",
    )
    messages = [{"role": "user", "content": prompt}]
    # Generous budget: the default architect is a thinking model and reasoning
    # tokens count against the completion limit.
    blueprint = client.structured(
        model, messages, "PanelBlueprint", BLUEPRINT_SCHEMA,
        max_completion_tokens=12000, ledger=ledger, stage="architect",
    )

    total = sum(d["count"] for d in blueprint["disciplines"])
    if total != panel_size:
        logger.warning("Blueprint seat count %d != %d; requesting correction", total, panel_size)
        messages.append({"role": "assistant", "content": str(blueprint)})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your discipline counts sum to {total}, but the panel must have exactly "
                    f"{panel_size} seats. Rebalance the counts (same disciplines unless one must "
                    f"go) so they sum to exactly {panel_size} and return the corrected JSON."
                ),
            }
        )
        blueprint = client.structured(
            model, messages, "PanelBlueprint", BLUEPRINT_SCHEMA,
            max_completion_tokens=12000, ledger=ledger, stage="architect",
        )
        total = sum(d["count"] for d in blueprint["disciplines"])
        if total != panel_size:
            # Deterministic rebalance: trim/pad the largest discipline
            diff = panel_size - total
            largest = max(blueprint["disciplines"], key=lambda d: d["count"])
            largest["count"] = max(1, largest["count"] + diff)
    return blueprint

"""Stage 2: generate personas per discipline in parallel batches, then dedupe."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prompts.loader import render

logger = logging.getLogger(__name__)

PERSONA_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "personas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "background": {"type": "string"},
                    "focus_areas": {"type": "array", "items": {"type": "string"}},
                    "perspective": {"type": "string"},
                },
                "required": ["name", "title", "background", "focus_areas", "perspective"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["personas"],
    "additionalProperties": False,
}


def _norm_key(persona):
    return re.sub(r"[^a-z0-9]+", "", (persona.get("title", "") + persona.get("name", "")).lower())


def generate_personas(client, model, problem, blueprint, guardrails, concurrency, ledger, on_persona=None):
    disciplines = blueprint["disciplines"]
    contrarians = blueprint.get("mandatedContrarians", [])
    all_names = [d["name"] for d in disciplines]
    pinned = list((guardrails or {}).get("pinnedExperts") or [])

    def build_batch(idx, disc):
        contrarian_note = ""
        if idx == 0 and contrarians:
            stances = "; ".join(c["stance"] for c in contrarians)
            contrarian_note = (
                f"- This discipline must also include the panel's contrarian seats with these "
                f"stances: {stances}"
            )
        pinned_note = ""
        if idx == 0 and pinned:
            pinned_note = f" The client requires these exact expert types as seats: {', '.join(pinned)}."
        prompt = render(
            "panel/persona_batch",
            count=disc["count"],
            discipline=disc["name"],
            problem=problem,
            rationale=disc["rationale"] + pinned_note,
            industries=", ".join(disc.get("industries") or []) or "any relevant",
            seniority_mix=disc.get("seniorityMix", "mixed"),
            contrarian_note=contrarian_note,
            other_disciplines=", ".join(n for n in all_names if n != disc["name"]),
        )
        batch = client.structured(
            model,
            [{"role": "user", "content": prompt}],
            "PersonaBatch",
            PERSONA_BATCH_SCHEMA,
            ledger=ledger,
            stage="personas",
        )
        personas = batch.get("personas", [])[: disc["count"]]
        for p in personas:
            p["discipline"] = disc["name"]
        return personas

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(build_batch, i, d): d for i, d in enumerate(disciplines)}
        for fut in as_completed(futures):
            disc = futures[fut]
            try:
                batch = fut.result()
            except Exception:
                logger.exception("Persona batch failed for discipline %s", disc["name"])
                batch = []
            results.extend(batch)
            if on_persona:
                for p in batch:
                    on_persona(p)

    seen, deduped = set(), []
    for p in results:
        key = _norm_key(p)
        if key in seen:
            logger.info("Dropping duplicate persona %s", p.get("name"))
            continue
        seen.add(key)
        deduped.append(p)
    return deduped

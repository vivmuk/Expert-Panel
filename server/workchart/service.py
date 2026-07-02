"""Work Chart v2: server-side generation, clarify→refine flow, revisions, and
the breakthrough-opportunities (type-2 thinking) layer."""
import json
import logging

from ..config import Config
from ..db import engagements as store
from ..prompts.loader import render
from ..venice.models import get_catalog
from .schemas import BREAKTHROUGH_SCHEMA, GENERATE_SCHEMA, REFINED_SCHEMA, REVISE_SCHEMA

logger = logging.getLogger(__name__)


def run_workchart(run, client, payload, ledger):
    """Full interactive flow, executed inside the runner thread."""
    catalog = get_catalog()
    model = catalog.resolve_role("workchart", (payload.get("models") or {}).get("workchart"))
    breakthrough_model = catalog.resolve_role(
        "breakthrough", (payload.get("models") or {}).get("breakthrough")
    )

    input_data = payload.get("input") or {}
    instruction = (input_data.get("instruction") or "").strip()

    if instruction and payload.get("engagementId"):
        return _revise(run, client, model, breakthrough_model, payload, instruction, ledger)
    return _generate(run, client, model, breakthrough_model, payload, ledger)


def _generate(run, client, model, breakthrough_model, payload, ledger):
    input_data = payload.get("input") or {}
    process_description = input_data.get("problem") or input_data.get("processDescription", "")
    run.emit(
        "run.started",
        {"runId": run.id, "mode": "workchart", "stages": ["draft", "clarify", "refine", "breakthrough"]},
    )

    run.emit("stage.started", {"stage": "draft"})
    prompt = render(
        "workchart/generate",
        process_description=process_description,
        industry=input_data.get("industry") or "not specified",
        constraints=input_data.get("constraints") or "none specified",
    )
    draft = client.structured(
        model,
        [{"role": "user", "content": prompt}],
        "WorkChartDraft",
        GENERATE_SCHEMA,
        max_completion_tokens=16000,
        ledger=ledger,
        stage="workchart",
    )
    run.emit("chart.draft", {"chart": _public_chart(draft)})
    run.emit("stage.completed", {"stage": "draft", "usage": _usage(ledger)})

    questions = draft.get("questions") or []
    chart = draft
    if questions:
        run.emit("clarify", {"questions": questions})
        try:
            answers = run.wait_for_answers(Config.RUN_ANSWER_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("Run %s: no clarifying answers; keeping draft", run.id)
            answers = None
        if answers:
            run.emit("stage.started", {"stage": "refine"})
            answers_block = "\n".join(
                f"Q ({q['id']}): {q['question']}\nA: {answers.get(q['id'], 'no answer provided')}"
                for q in questions
            )
            refine_prompt = render(
                "workchart/refine",
                process_description=process_description,
                draft_json=json.dumps(_public_chart(draft))[:40000],
                answers_block=answers_block,
            )
            chart = client.structured(
                model,
                [{"role": "user", "content": refine_prompt}],
                "WorkChartRefined",
                REFINED_SCHEMA,
                max_completion_tokens=16000,
                ledger=ledger,
                stage="workchart",
            )
            chart["questions"] = questions
            chart["answers"] = answers
            run.emit("stage.completed", {"stage": "refine", "usage": _usage(ledger)})

    chart["breakthroughOpportunities"] = _breakthroughs(
        run, client, breakthrough_model, chart, process_description, ledger
    )
    chart["processDescription"] = process_description
    run.emit("chart.final", {"chart": _public_chart(chart)})
    return chart


def _revise(run, client, model, breakthrough_model, payload, instruction, ledger):
    engagement_id = payload["engagementId"]
    engagement = store.get_engagement(engagement_id)
    latest = (engagement or {}).get("latest") or {}
    current_chart = latest.get("result")
    if not current_chart:
        raise ValueError(f"Engagement {engagement_id} has no chart to revise")

    process_description = current_chart.get("processDescription", "")
    run.emit("run.started", {"runId": run.id, "mode": "workchart", "stages": ["revise", "breakthrough"]})
    run.emit("stage.started", {"stage": "revise"})
    prompt = render(
        "workchart/revise",
        chart_json=json.dumps(_public_chart(current_chart))[:60000],
        instruction=instruction,
    )
    revised = client.structured(
        model,
        [{"role": "user", "content": prompt}],
        "WorkChartRevised",
        REVISE_SCHEMA,
        max_completion_tokens=16000,
        ledger=ledger,
        stage="workchart",
    )
    run.emit("stage.completed", {"stage": "revise", "usage": _usage(ledger)})

    revised["breakthroughOpportunities"] = _breakthroughs(
        run, client, breakthrough_model, revised, process_description, ledger
    )
    revised["processDescription"] = process_description
    revised["revisionInstruction"] = instruction
    run.emit("chart.final", {"chart": _public_chart(revised)})
    return revised


def _breakthroughs(run, client, model, chart, process_description, ledger):
    run.emit("stage.started", {"stage": "breakthrough"})
    prompt = render(
        "workchart/breakthrough",
        chart_json=json.dumps(
            {
                "currentProcess": chart.get("currentProcess"),
                "futureProcess": chart.get("futureProcess"),
                "deltas": chart.get("deltas"),
                "agentFactory": chart.get("agentFactory"),
            }
        )[:50000],
        process_description=process_description,
    )
    try:
        result = client.structured(
            model,
            [{"role": "user", "content": prompt}],
            "BreakthroughOpportunities",
            BREAKTHROUGH_SCHEMA,
            max_completion_tokens=8000,
            temperature=0.9,
            ledger=ledger,
            stage="breakthrough",
        )
        opportunities = result.get("opportunities", [])
    except Exception:
        logger.exception("Breakthrough generation failed; chart proceeds without it")
        opportunities = []
    run.emit("breakthrough.ready", {"opportunities": opportunities})
    run.emit("stage.completed", {"stage": "breakthrough", "usage": _usage(ledger)})
    return opportunities


def _public_chart(chart):
    return {k: v for k, v in chart.items() if k != "answers" or v}


def _usage(ledger):
    return {"totalCostUsd": round(ledger.total_cost_usd, 6)}

"""EngagementRunner: executes a mode's flow on a background thread, emitting
SSE events and persisting the result as an engagement revision."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import Config
from ..db import engagements as store
from ..modes import get_mode
from ..prompts.loader import render
from ..venice.client import get_client
from ..venice.models import get_catalog
from ..venice.usage import UsageLedger
from . import architect, insights, market_intel, synthesis
from .estimate import estimate_run
from .events import REGISTRY

logger = logging.getLogger(__name__)


class CostCircuitBreaker(Exception):
    pass


def start_run(payload):
    """Validate, create engagement + run, and launch the worker thread.
    Returns (run, engagement_id, estimate)."""
    mode = get_mode(payload.get("mode", "deep_dive"))
    if not mode.available:
        raise ValueError(f"Mode {mode.id} is not available yet")

    problem = (payload.get("input") or {}).get("problem", "").strip()
    if not problem:
        raise ValueError("input.problem is required")

    panel_size = int((payload.get("panel") or {}).get("size") or mode.default_panel_size)
    panel_size = max(3, min(panel_size, mode.max_panel_size, Config.MAX_PANEL_SIZE))

    est = estimate_run(mode.id, panel_size, payload.get("models") or {})

    engagement_id = payload.get("engagementId")
    title = problem[:80] + ("…" if len(problem) > 80 else "")
    if engagement_id:
        existing = store.get_engagement(engagement_id)
        if not existing:
            raise ValueError(f"Engagement {engagement_id} not found")
        store.set_status(engagement_id, "running")
    else:
        engagement_id = store.create_engagement(mode.id, title)

    run = REGISTRY.create(mode.id, engagement_id)
    thread = threading.Thread(
        target=_execute,
        args=(run, mode, payload, problem, panel_size, est),
        daemon=True,
        name=f"run-{run.id}",
    )
    thread.start()
    return run, engagement_id, est


def _execute(run, mode, payload, problem, panel_size, est):
    client = get_client()
    catalog = get_catalog()
    ledger = UsageLedger(pricing_lookup=catalog.pricing)
    budget_limit = max(est["totalCostUsd"], 0.05) * Config.COST_CIRCUIT_BREAKER_MULTIPLIER

    def check_budget():
        if ledger.total_cost_usd > budget_limit:
            raise CostCircuitBreaker(
                f"Run spend ${ledger.total_cost_usd:.2f} exceeded {Config.COST_CIRCUIT_BREAKER_MULTIPLIER}x "
                f"the ${est['totalCostUsd']:.2f} estimate; aborting."
            )

    try:
        models = {
            "architect": catalog.resolve_role("architect", (payload.get("models") or {}).get("architect")),
            "persona_writer": catalog.resolve_role("persona_writer", (payload.get("models") or {}).get("persona_writer")),
            "expert": catalog.resolve_role(
                "pulse" if mode.quantitative else "expert",
                (payload.get("models") or {}).get("expert"),
            ),
            "market_agent": catalog.resolve_role("market_agent", (payload.get("models") or {}).get("market_agent")),
            "synthesizer": catalog.resolve_role("synthesizer", (payload.get("models") or {}).get("synthesizer")),
        }

        if mode.flow == "workchart":
            from ..workchart.service import run_workchart

            result = run_workchart(run, client, payload, ledger)
        elif mode.flow == "board":
            result = _board_flow(run, client, mode, models, payload, problem, panel_size, ledger, check_budget)
        else:
            result = _panel_flow(run, client, mode, models, payload, problem, panel_size, ledger, check_budget)

        usage = ledger.totals()
        rev = store.add_revision(
            run.engagement_id,
            payload,
            result=result,
            usage=usage,
            note=(payload.get("note") or "generated"),
            cost_usd=usage["total_cost_usd"],
        )
        store.set_status(run.engagement_id, "completed")
        run.result = result
        run.status = "completed"
        run.emit("run.completed", {"engagementId": run.engagement_id, "revision": rev, "usage": usage})
    except Exception as exc:
        logger.exception("Run %s failed", run.id)
        run.status = "failed"
        run.error = str(exc)
        store.set_status(run.engagement_id, "failed")
        run.emit("run.error", {"message": str(exc), "stage": run.mode})
    finally:
        try:
            store.save_run_events(run.id, run.events)
        except Exception:
            logger.exception("Failed to flush run events for %s", run.id)


# --------------------------------------------------------------- panel flow
def _panel_flow(run, client, mode, models, payload, problem, panel_size, ledger, check_budget):
    search_opts = payload.get("search") or {}
    guardrails = payload.get("panel") or {}
    concurrency = Config.PANEL_CONCURRENCY

    stages = ["architect", "personas", "market", "insights", "synthesis"]
    if not mode.include_market_intel or search_opts.get("web") is False:
        stages.remove("market")
    run.emit("run.started", {"runId": run.id, "mode": mode.id, "panelSize": panel_size, "stages": stages})

    # Scrape client URLs first so the architect sees the context
    context_docs = []
    urls = (payload.get("input") or {}).get("urls") or []
    if urls and search_opts.get("scrapeUrls", True):
        context_docs = market_intel.scrape_context(client, urls)

    # Stage 1 — blueprint
    run.emit("stage.started", {"stage": "architect"})
    mode_guardrails = dict(guardrails)
    if mode.mode_brief:
        seed = mode_guardrails.get("seedPerspectives") or ""
        mode_guardrails["seedPerspectives"] = f"{mode.mode_brief}\n{seed}".strip()
    blueprint = architect.design_blueprint(
        client, models["architect"], problem, panel_size, mode_guardrails, context_docs, ledger
    )
    run.emit("blueprint.ready", {"blueprint": blueprint})
    run.emit("stage.completed", {"stage": "architect", "usage": _stage_usage(ledger, "architect")})
    check_budget()

    # Stage 2 — personas
    run.emit("stage.started", {"stage": "personas", "expectedItems": panel_size})
    persona_list = personas_stage(run, client, models["persona_writer"], problem, blueprint, mode_guardrails, concurrency, ledger)
    run.emit("stage.completed", {"stage": "personas", "usage": _stage_usage(ledger, "personas")})
    check_budget()

    # Stage 3 — market intelligence (before insights so experts get the digest)
    market_briefs = []
    if "market" in stages:
        run.emit("stage.started", {"stage": "market", "expectedItems": 5})
        market_briefs = market_intel.gather_market_intelligence(
            client,
            models["architect"],
            models["market_agent"],
            problem,
            enable_x=bool(search_opts.get("x")),
            concurrency=min(concurrency, 4),
            ledger=ledger,
            on_planned=lambda topics: run.emit("market.planned", {"topics": topics}),
            on_completed=lambda b: run.emit(
                "market.completed",
                {"topic": b["topic"], "channel": b["channel"], "findings": b["findings"], "citations": b["citations"]},
            ),
        )
        run.emit("stage.completed", {"stage": "market", "usage": _stage_usage(ledger, "market")})
        check_budget()

    # Stage 4 — expert insights
    run.emit("stage.started", {"stage": "insights", "expectedItems": len(persona_list)})
    digest = market_intel.digest(market_briefs) if market_briefs else None
    insight_entries = insights.collect_insights(
        client,
        models["expert"],
        problem,
        persona_list,
        concurrency,
        ledger,
        market_digest=digest,
        prompt_name=mode.insight_prompt,
        schema=mode.insight_schema,
        on_started=lambda i, p: run.emit("expert.started", {"index": i, "personaName": p["name"]}),
        on_completed=lambda i, e: run.emit(
            "expert.completed",
            {"index": i, "personaName": e["persona"]["name"], "insight": _public_insight(e)},
        ),
        cancel_event=run.cancel_requested,
    )
    run.emit("stage.completed", {"stage": "insights", "usage": _stage_usage(ledger, "insights")})
    check_budget()

    result = {
        "problem": problem,
        "blueprint": blueprint,
        "personas": persona_list,
        "insights": insight_entries,
        "market_intelligence": market_briefs,
    }

    # Stage 5 — synthesis (or quantitative aggregation for pulse modes)
    if mode.quantitative:
        result["aggregates"] = _pulse_aggregates(insight_entries)
        run.emit("pulse.batch", {"completed": len(insight_entries), "total": len(insight_entries), "aggregates": result["aggregates"]})
    else:
        run.emit("stage.started", {"stage": "synthesis"})
        result["synthesis"] = synthesis.synthesize(
            client, models["synthesizer"], problem, insight_entries, market_briefs, panel_size, ledger
        )
        run.emit("stage.completed", {"stage": "synthesis", "usage": _stage_usage(ledger, "synthesis")})

    return result


def personas_stage(run, client, model, problem, blueprint, guardrails, concurrency, ledger):
    counter = {"n": 0}

    def on_persona(p):
        counter["n"] += 1
        run.emit("persona.created", {"index": counter["n"], "persona": p})

    from .personas import generate_personas

    return generate_personas(client, model, problem, blueprint, guardrails, concurrency, ledger, on_persona=on_persona)


def _public_insight(entry):
    return {k: v for k, v in entry.items() if k != "persona"}


def _stage_usage(ledger, stage):
    totals = ledger.totals()["by_stage"].get(stage) or {}
    return {
        "promptTokens": totals.get("prompt_tokens", 0),
        "completionTokens": totals.get("completion_tokens", 0),
        "costUsd": totals.get("cost_usd", 0.0),
        "totalCostUsd": round(ledger.total_cost_usd, 6),
    }


def _pulse_aggregates(insight_entries):
    stances, concerns, by_discipline = [], [], {}
    for e in insight_entries:
        if "stance" not in e:
            continue
        stances.append(e["stance"])
        concerns.append(e.get("top_concern", ""))
        disc = e.get("persona", {}).get("discipline", "Other")
        by_discipline.setdefault(disc, []).append(e["stance"])
    if not stances:
        return {"count": 0}
    distribution = {str(v): stances.count(v) for v in range(1, 6)}
    return {
        "count": len(stances),
        "mean_stance": round(sum(stances) / len(stances), 2),
        "distribution": distribution,
        "support_pct": round(100 * len([s for s in stances if s >= 4]) / len(stances), 1),
        "oppose_pct": round(100 * len([s for s in stances if s <= 2]) / len(stances), 1),
        "by_discipline": {
            d: round(sum(v) / len(v), 2) for d, v in sorted(by_discipline.items())
        },
        "top_concerns": concerns[:20],
    }


# --------------------------------------------------------------- board flow
BOARD_MINUTES_SCHEMA = {
    "type": "object",
    "properties": {
        "motion": {"type": "string"},
        "member_positions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "evolution": {"type": "string"},
                    "vote": {"type": "string", "enum": ["for", "against", "abstain"]},
                },
                "required": ["member", "evolution", "vote"],
                "additionalProperties": False,
            },
        },
        "decisive_arguments": {"type": "array", "items": {"type": "string"}},
        "resolution": {"type": "string"},
        "conditions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["motion", "member_positions", "decisive_arguments", "resolution", "conditions"],
    "additionalProperties": False,
}


def _board_flow(run, client, mode, models, payload, problem, panel_size, ledger, check_budget):
    concurrency = min(Config.PANEL_CONCURRENCY, panel_size)
    rounds = int((payload.get("board") or {}).get("rounds", 3))
    rounds = max(2, min(rounds, 4))
    run.emit(
        "run.started",
        {"runId": run.id, "mode": mode.id, "panelSize": panel_size, "stages": ["architect", "personas", "debate", "minutes"]},
    )

    run.emit("stage.started", {"stage": "architect"})
    guardrails = dict(payload.get("panel") or {})
    guardrails["seedPerspectives"] = f"{mode.mode_brief}\n{guardrails.get('seedPerspectives') or ''}".strip()
    blueprint = architect.design_blueprint(client, models["architect"], problem, panel_size, guardrails, [], ledger)
    run.emit("blueprint.ready", {"blueprint": blueprint})
    run.emit("stage.completed", {"stage": "architect", "usage": _stage_usage(ledger, "architect")})

    run.emit("stage.started", {"stage": "personas", "expectedItems": panel_size})
    members = personas_stage(run, client, models["persona_writer"], problem, blueprint, guardrails, concurrency, ledger)
    run.emit("stage.completed", {"stage": "personas", "usage": _stage_usage(ledger, "personas")})
    check_budget()

    transcript = []  # [{round, speaker, statement}]
    run.emit("stage.started", {"stage": "debate", "expectedItems": rounds * len(members)})

    def speak(member, round_no):
        if round_no == 1:
            prompt = render(
                "modes/board_opening",
                name=member["name"],
                title=member.get("title", ""),
                background=member.get("background", ""),
                perspective=member.get("perspective", ""),
                problem=problem,
            )
        else:
            recent = "\n\n".join(
                f"{t['speaker']}: {t['statement']}" for t in transcript if t["round"] == round_no - 1
            )
            prompt = render(
                "modes/board_response",
                name=member["name"],
                title=member.get("title", ""),
                background=member.get("background", ""),
                perspective=member.get("perspective", ""),
                problem=problem,
                transcript=recent[:20000],
            )
        deltas = client.chat_stream(
            models["expert"],
            [{"role": "user", "content": prompt}],
            max_completion_tokens=500,
            on_usage=lambda u: ledger.record("debate", models["expert"], u),
        )
        return "".join(deltas)

    for round_no in range(1, rounds + 1):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(speak, m, round_no): m for m in members}
            for fut in as_completed(futures):
                member = futures[fut]
                try:
                    statement = fut.result()
                except Exception as exc:
                    logger.exception("Board member %s failed to speak", member["name"])
                    statement = f"(unable to respond: {exc})"
                turn = {"round": round_no, "speaker": member["name"], "statement": statement}
                transcript.append(turn)
                run.emit("board.turn", turn)
        check_budget()
    run.emit("stage.completed", {"stage": "debate", "usage": _stage_usage(ledger, "debate")})

    run.emit("stage.started", {"stage": "minutes"})
    full = "\n\n".join(f"[Round {t['round']}] {t['speaker']}: {t['statement']}" for t in transcript)
    minutes = client.structured(
        models["synthesizer"],
        [{"role": "user", "content": render("modes/board_minutes", problem=problem, transcript=full[:80000])}],
        "BoardMinutes",
        BOARD_MINUTES_SCHEMA,
        max_completion_tokens=4000,
        ledger=ledger,
        stage="minutes",
    )
    run.emit("stage.completed", {"stage": "minutes", "usage": _stage_usage(ledger, "minutes")})

    return {"problem": problem, "blueprint": blueprint, "members": members, "transcript": transcript, "minutes": minutes}

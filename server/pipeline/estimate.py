"""Pre-run cost estimation: heuristic tokens-per-call constants × live pricing."""
from ..config import Config
from ..venice.models import get_catalog

# (calls, prompt tokens per call, completion tokens per call) heuristics per stage
def _stage_profile(mode_id, panel_size):
    if mode_id == "quick_pulse":
        return {
            "architect": (1, 1500, 1200),
            "personas": (max(4, panel_size // 8), 1200, 2500),
            "insights": (panel_size, 800, 250),
        }
    if mode_id == "board_meeting":
        rounds = 3
        return {
            "architect": (1, 1500, 1200),
            "personas": (3, 1200, 2500),
            "debate": (panel_size * rounds, 2500, 400),
            "minutes": (1, 8000, 2500),
        }
    if mode_id == "workchart":
        return {
            "workchart": (2, 3000, 8000),
            "breakthrough": (1, 4000, 3000),
        }
    profile = {
        "architect": (1, 1800, 1500),
        "personas": (max(4, panel_size // 4), 1400, 2500),
        "market": (6, 2500, 1500),
        "insights": (panel_size, 1800, 1500),
        "synthesis": (1 if panel_size <= 30 else 10, 20000 if panel_size <= 30 else 8000, 6000 if panel_size <= 30 else 2000),
    }
    return profile


def _role_for_stage(stage, mode_id):
    mapping = {
        "architect": "architect",
        "personas": "persona_writer",
        "market": "market_agent",
        "insights": "pulse" if mode_id == "quick_pulse" else "expert",
        "synthesis": "synthesizer",
        "debate": "expert",
        "minutes": "synthesizer",
        "workchart": "workchart",
        "breakthrough": "breakthrough",
    }
    return mapping.get(stage, "expert")


def estimate_run(mode_id, panel_size, model_overrides=None):
    catalog = get_catalog()
    model_overrides = model_overrides or {}
    stages = []
    total = 0.0
    for stage, (calls, tok_in, tok_out) in _stage_profile(mode_id, panel_size).items():
        role = _role_for_stage(stage, mode_id)
        try:
            model = catalog.resolve_role(
                role if role in Config.MODEL_ROLE_DEFAULTS else "expert",
                model_overrides.get(role),
            )
            pricing = catalog.pricing(model) or {"input": 0.7, "output": 2.8}
        except Exception:
            model = Config.MODEL_ROLE_DEFAULTS.get(role, "unknown")
            pricing = {"input": 0.7, "output": 2.8}
        cost = calls * ((tok_in / 1e6) * pricing["input"] + (tok_out / 1e6) * pricing["output"])
        total += cost
        stages.append(
            {
                "stage": stage,
                "model": model,
                "calls": calls,
                "estTokensIn": calls * tok_in,
                "estTokensOut": calls * tok_out,
                "estCostUsd": round(cost, 4),
            }
        )
    return {"mode": mode_id, "panelSize": panel_size, "stages": stages, "totalCostUsd": round(total, 4)}

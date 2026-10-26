"""Pre-stages: structured artifacts produced before the panel runs.

A pre-stage gives the personas something concrete to attack instead of a blank
prompt. Both return (artifact, brief_block) where brief_block is plain text that
is appended to the engagement brief for the architect and the experts.
"""
import json
import logging

from ..prompts.loader import render

logger = logging.getLogger(__name__)

SCENARIOS_SCHEMA = {
    "type": "object",
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "thesis": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "likelihood": {"type": "string", "enum": ["low", "plausible", "likely"]},
                    "triggers": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
                    "economics": {"type": "string"},
                    "what_a_strategy_assuming_today_gets_wrong": {"type": "string"},
                },
                "required": [
                    "name", "thesis", "timeframe", "likelihood", "triggers", "economics",
                    "what_a_strategy_assuming_today_gets_wrong",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scenarios"],
    "additionalProperties": False,
}

TWIN_SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string"},
        "data_feeds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_system": {"type": "string"},
                    "cadence": {"type": "string"},
                    "latency_tolerance": {"type": "string"},
                    "owner": {"type": "string"},
                    "if_stale": {"type": "string"},
                },
                "required": ["name", "source_system", "cadence", "latency_tolerance", "owner", "if_stale"],
                "additionalProperties": False,
            },
        },
        "simulation_surface": {
            "type": "object",
            "properties": {
                "state_variables": {"type": "array", "items": {"type": "string"}},
                "fidelity": {"type": "string"},
                "simplifications": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["state_variables", "fidelity", "simplifications"],
            "additionalProperties": False,
        },
        "decision_loops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "trigger": {"type": "string"},
                    "decision": {"type": "string"},
                    "cadence": {"type": "string"},
                    "actor": {"type": "string", "enum": ["human", "agent", "hybrid"]},
                    "guardrail": {"type": "string"},
                },
                "required": ["name", "trigger", "decision", "cadence", "actor", "guardrail"],
                "additionalProperties": False,
            },
        },
        "agents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "observes": {"type": "string"},
                    "decides": {"type": "string"},
                    "may_change": {"type": "string"},
                },
                "required": ["name", "observes", "decides", "may_change"],
                "additionalProperties": False,
            },
        },
        "governance": {
            "type": "object",
            "properties": {
                "access": {"type": "string"},
                "residency": {"type": "string"},
                "model_risk": {"type": "string"},
                "audit": {"type": "string"},
                "kill_switch": {"type": "string"},
            },
            "required": ["access", "residency", "model_risk", "audit", "kill_switch"],
            "additionalProperties": False,
        },
        "first_90_days": {"type": "string"},
        "failure_modes": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
    },
    "required": [
        "scope", "data_feeds", "simulation_surface", "decision_loops", "agents",
        "governance", "first_90_days", "failure_modes",
    ],
    "additionalProperties": False,
}


def generate_scenarios(client, model, problem, count, ledger):
    """Return (scenarios_artifact, brief_block)."""
    prompt = render("modes/scenario_generate", problem=problem, scenario_count=count)
    artifact = client.structured(
        model,
        [{"role": "user", "content": prompt}],
        "Scenarios",
        SCENARIOS_SCHEMA,
        max_completion_tokens=4000,
        ledger=ledger,
        stage="scenarios",
    )
    lines = []
    for i, s in enumerate(artifact.get("scenarios", []), 1):
        lines.append(
            f"{i}. **{s['name']}** ({s['timeframe']}, {s['likelihood']}): {s['thesis']}\n"
            f"   Triggers: {'; '.join(s['triggers'])}\n"
            f"   Economics: {s['economics']}\n"
            f"   A strategy assuming today gets wrong: {s['what_a_strategy_assuming_today_gets_wrong']}"
        )
    block = (
        "## Scenarios under test\n"
        "Judge the strategy separately in each world below. Verdicts must use these names.\n\n"
        + "\n\n".join(lines)
    )
    return artifact, block


def design_twin(client, model, problem, horizon, ledger):
    """Return (twin_artifact, brief_block)."""
    prompt = render("modes/twin_generate", problem=problem, horizon=horizon)
    artifact = client.structured(
        model,
        [{"role": "user", "content": prompt}],
        "DigitalTwinDraft",
        TWIN_SCHEMA,
        max_completion_tokens=6000,
        ledger=ledger,
        stage="twin",
    )
    block = "## Draft digital twin (v0)\n```json\n" + json.dumps(artifact, indent=2)[:24000] + "\n```"
    return artifact, block


PRESTAGES = {
    "scenarios": generate_scenarios,
    "twin": design_twin,
}

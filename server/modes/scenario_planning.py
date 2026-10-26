"""Scenario Planning — generate the futures first, then stress the strategy
against every one of them. Pre-stage: `scenarios`."""
from .base import ModeSpec, insight_schema, register

SCENARIO_INSIGHT_SCHEMA = insight_schema(
    {
        "scenario_verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["robust", "fragile", "fatal"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["scenario", "verdict", "reasoning"],
                "additionalProperties": False,
            },
        }
    }
)

register(
    ModeSpec(
        id="scenario_planning",
        name="Scenario Planning",
        description="War-game 3-5 futures: experts stress your strategy against each scenario and identify robust moves and early-warning signals.",
        default_panel_size=14,
        pre_stage="scenarios",
        insight_prompt="modes/scenario_stress",
        insight_schema=SCENARIO_INSIGHT_SCHEMA,
        synthesis_prompt="modes/scenario_synthesis",
        extra_fields=("scenario_verdicts",),
        result_kind="scenarios",
        defaults={"scenarios": 4},
        mode_brief=(
            "Staff a strategy panel that has lived through regime change: a scenario planner, "
            "a macro economist, a competitor strategist, a supply-chain operator, a regulator, "
            "and an investor who has funded both winners and losers in this category."
        ),
    )
)

"""Digital Twin Blueprint — draft the twin first, then have the panel tear it
apart and turn it into an implementation plan. Pre-stage: `twin`."""
from .base import ModeSpec, insight_schema, register

TWIN_CRITIQUE_SCHEMA = insight_schema(
    {
        "twin_element": {
            "type": "string",
            "enum": ["data feed", "simulation surface", "decision loop", "agents", "governance"],
        },
        "failure_mode": {"type": "string"},
        "fix": {"type": "string"},
    }
)

register(
    ModeSpec(
        id="digital_twin",
        name="Digital Twin Blueprint",
        description="Design the digital twin of a business unit: data feeds, simulation surface, decision loops, and the agents that keep it alive.",
        default_panel_size=12,
        pre_stage="twin",
        insight_prompt="modes/twin_critique",
        insight_schema=TWIN_CRITIQUE_SCHEMA,
        synthesis_prompt="modes/twin_plan",
        extra_fields=("twin_element", "failure_mode"),
        result_kind="twin",
        include_market_intel=False,
        defaults={"horizon": "12 months"},
        mode_brief=(
            "Staff a twin-building crew: a systems architect, a data engineer, a simulation/OR modeller, "
            "a control-theory or RL practitioner, an operations owner, and a security/governance lead."
        ),
    )
)

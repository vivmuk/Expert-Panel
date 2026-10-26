"""AI Opportunity Scan — map functions to agent opportunities, scored for value
and feasibility, then ranked into a first-90-days sequence."""
from .base import ModeSpec, insight_schema, register

OPPORTUNITY_SCHEMA = insight_schema(
    {
        "function_area": {"type": "string"},
        "mechanism": {
            "type": "string",
            "enum": ["agent_factory", "digital_twin", "workflow_automation", "copilot", "analytics"],
        },
        "value_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "feasibility_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "time_to_value": {"type": "string", "enum": ["<90 days", "3-6 months", "6-12 months", ">12 months"]},
        "data_dependency": {"type": "string"},
    }
)

register(
    ModeSpec(
        id="ai_opportunity_scan",
        name="AI Opportunity Scan",
        description="Map your org's functions to agent opportunities: where agent factories, digital twins, and automation create the most value first.",
        default_panel_size=14,
        insight_prompt="modes/opportunity_insight",
        insight_schema=OPPORTUNITY_SCHEMA,
        synthesis_prompt="modes/opportunity_map",
        extra_fields=("function_area", "mechanism", "value_score", "feasibility_score", "time_to_value"),
        result_kind="opportunities",
        include_market_intel=False,
        mode_brief=(
            "Staff an operating committee plus operators who have actually shipped agents: a COO, "
            "a CIO/CDAO, a head of shared services, a data-platform lead, a process-reengineering lead, "
            "and a frontline manager who has to live with the change."
        ),
    )
)

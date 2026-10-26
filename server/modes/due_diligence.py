"""Due Diligence — workstream-split diligence with severity-rated findings and a
memo. Each expert owns a workstream and must state what would kill the deal."""
from .base import ModeSpec, insight_schema, register

DILIGENCE_SCHEMA = insight_schema(
    {
        "workstream": {"type": "string"},
        "severity": {"type": "string", "enum": ["deal_breaker", "material", "monitor", "cosmetic"]},
        "open_questions": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
        "evidence_gap": {"type": "string"},
    }
)

register(
    ModeSpec(
        id="due_diligence",
        name="Due Diligence",
        description="A diligence team works the target from every angle — financials, tech, team, market, legal — and returns a findings memo with deal risks.",
        default_panel_size=12,
        insight_prompt="modes/diligence_insight",
        insight_schema=DILIGENCE_SCHEMA,
        synthesis_prompt="modes/diligence_memo",
        extra_fields=("workstream", "severity", "evidence_gap"),
        result_kind="diligence",
        defaults={"workstreams": "financial, technical, commercial, legal/regulatory, people/org"},
        mode_brief=(
            "Staff a diligence team, one senior expert per workstream: financial (quality of earnings, "
            "unit economics), technical (architecture, security, scalability, tech debt), commercial "
            "(pricing, pipeline, churn, competition), legal/regulatory (IP, contracts, licences, privacy), "
            "and people/organisation (key-person risk, culture, retention). Each owns only their workstream."
        ),
    )
)

"""Quick Pulse — 50-100 lightweight personas, quantitative aggregation, no synthesis."""
from .base import ModeSpec, register

PULSE_SCHEMA = {
    "type": "object",
    "properties": {
        "stance": {"type": "integer", "minimum": 1, "maximum": 5},
        "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
        "one_liner": {"type": "string"},
        "top_concern": {"type": "string"},
    },
    "required": ["stance", "confidence", "one_liner", "top_concern"],
    "additionalProperties": False,
}

register(
    ModeSpec(
        id="quick_pulse",
        name="Quick Pulse",
        description="Survey 50-100 lightweight expert personas for a quantitative read: stance distribution, confidence, and the top concerns, in minutes.",
        default_panel_size=50,
        insight_prompt="modes/quick_pulse",
        insight_schema=PULSE_SCHEMA,
        quantitative=True,
        include_market_intel=False,
        result_kind="pulse",
    )
)

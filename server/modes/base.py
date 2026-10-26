"""Mode registry.

A mode is a *module*: it registers a ModeSpec (sizing, flow, prompts, schemas)
and ships its own prompt markdown. Adding a mode should never require editing
the runner — only registering a spec here and dropping prompts in
`server/prompts/modes/`.

Flows are shared machinery:
  panel       architect → personas → [market] → insights → [synthesis | pulse]
  board       architect → personas → debate rounds → minutes
  workchart   generate → breakthroughs → revise
Pre-stages (optional) run before the panel and hand structured context forward:
  scenarios   generate 3-5 futures, then stress the strategy against each
  twin        draft a digital-twin spec, then have the panel critique it
"""
from dataclasses import dataclass, field


@dataclass
class ModeSpec:
    id: str
    name: str
    description: str
    available: bool = True
    flow: str = "panel"  # panel | board | workchart
    default_panel_size: int = 20
    max_panel_size: int = 100
    insight_prompt: str = "panel/expert_insight"
    insight_schema: dict = None
    mode_brief: str = ""  # injected into the architect's seed perspectives
    quantitative: bool = False  # pulse-style aggregation
    include_market_intel: bool = True
    synthesis_prompt: str = "panel/synthesis"
    pre_stage: str = ""  # "" | "scenarios" | "twin"
    extra_fields: tuple = ()  # insight fields surfaced to synthesis
    result_kind: str = "panel"  # lets the web app pick a report renderer
    defaults: dict = field(default_factory=dict)

    def to_public(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": "available" if self.available else "coming_soon",
            "flow": self.flow,
            "preStage": self.pre_stage or None,
            "resultKind": self.result_kind,
            "defaults": {
                "panelSize": self.default_panel_size,
                "maxPanelSize": self.max_panel_size,
                **self.defaults,
            },
        }


MODE_REGISTRY = {}


def register(spec):
    MODE_REGISTRY[spec.id] = spec
    return spec


def get_mode(mode_id):
    spec = MODE_REGISTRY.get(mode_id)
    if spec is None:
        raise KeyError(f"Unknown mode: {mode_id}")
    return spec


def modes():
    """Registered modes in display order (registration order)."""
    return list(MODE_REGISTRY.values())


def insight_schema(extra=None):
    """Standard expert-insight schema, optionally extended with mode-specific
    fields. `insights_and_analysis` is preserved because synthesis reads it."""
    item_props = {
        "insight": {"type": "string"},
        "supporting_reasoning": {"type": "string"},
        "confidence_level": {"type": "string", "enum": ["High", "Medium", "Low"]},
        "implementation_ideas": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "identified_risks": {"type": "array", "items": {"type": "string"}},
        "identified_opportunities": {"type": "array", "items": {"type": "string"}},
    }
    required = list(item_props)
    if extra:
        item_props.update(extra)
        required.extend(extra)  # mode-specific fields are mandatory in that mode
    return {
        "type": "object",
        "properties": {
            "insights_and_analysis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_props,
                    "required": required,
                    "additionalProperties": False,
                },
            }
        },
        "required": ["insights_and_analysis"],
        "additionalProperties": False,
    }

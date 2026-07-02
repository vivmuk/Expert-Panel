"""Mode registry. A mode parameterizes the shared panel machinery (prompts,
schemas, sizes, models) or points at a custom flow (work chart, board)."""
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
    defaults: dict = field(default_factory=dict)

    def to_public(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": "available" if self.available else "coming_soon",
            "flow": self.flow,
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

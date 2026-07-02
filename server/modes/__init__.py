from .base import MODE_REGISTRY, ModeSpec, get_mode, register

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
        id="deep_dive",
        name="Deep Dive Panel",
        description="A bespoke panel of experts dissects your problem: blueprint, individual analyses, live market intelligence, and a synthesized report with consensus and dissent.",
        default_panel_size=20,
    )
)

register(
    ModeSpec(
        id="red_team",
        name="Red Team",
        description="Adversarial experts — pre-mortem specialists, rival strategists, skeptical regulators — attack your plan and rank what could kill it, with mitigations.",
        default_panel_size=12,
        insight_prompt="modes/red_team_insight",
        mode_brief=(
            "This is an adversarial red-team engagement: staff the panel with attackers — "
            "a pre-mortem specialist, a competitor's chief strategist, a hostile regulator, a "
            "burned former customer, a short-seller analyst, security/legal skeptics."
        ),
    )
)

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
    )
)

register(
    ModeSpec(
        id="board_meeting",
        name="Board Meeting",
        description="A simulated board debates your motion across multiple rounds — opening positions, rebuttals, concessions — ending in minutes and a vote.",
        flow="board",
        default_panel_size=8,
        max_panel_size=12,
        include_market_intel=False,
        mode_brief=(
            "Staff a board of directors: CEO-type, CFO-type, CTO-type, independent directors "
            "with governance experience, an activist investor, and relevant domain outsiders."
        ),
    )
)

register(
    ModeSpec(
        id="workchart",
        name="Work Chart",
        description="Map a process today vs. its AI-agent future: owners, agent functions, reusable agent assets, time/cost/FTE deltas — plus breakthrough redesign opportunities.",
        flow="workchart",
        include_market_intel=False,
    )
)

# Coming soon — registered so they appear in the UI; lighting one up is a
# prompts + ModeSpec change only.
register(
    ModeSpec(
        id="scenario_planning",
        name="Scenario Planning",
        description="War-game 3-5 futures: experts stress your strategy against each scenario and identify robust moves and early-warning signals.",
        available=False,
    )
)
register(
    ModeSpec(
        id="due_diligence",
        name="Due Diligence",
        description="A diligence team works the target from every angle — financials, tech, team, market, legal — and returns a findings memo with deal risks.",
        available=False,
    )
)
register(
    ModeSpec(
        id="ai_opportunity_scan",
        name="AI Opportunity Scan",
        description="Map your org's functions to agent opportunities: where agent factories, digital twins, and automation create the most value first.",
        available=False,
    )
)
register(
    ModeSpec(
        id="digital_twin",
        name="Digital Twin Blueprint",
        description="Design the digital twin of a business unit: data feeds, simulation surface, decision loops, and the agents that keep it alive.",
        available=False,
    )
)

__all__ = ["MODE_REGISTRY", "ModeSpec", "get_mode", "register", "PULSE_SCHEMA"]

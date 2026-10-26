"""Red Team — adversarial panel that attacks a plan and ranks what kills it."""
from .base import ModeSpec, register

register(
    ModeSpec(
        id="red_team",
        name="Red Team",
        description="Adversarial experts — pre-mortem specialists, rival strategists, skeptical regulators — attack your plan and rank what could kill it, with mitigations.",
        default_panel_size=12,
        insight_prompt="modes/red_team_insight",
        result_kind="panel",
        mode_brief=(
            "This is an adversarial red-team engagement: staff the panel with attackers — "
            "a pre-mortem specialist, a competitor's chief strategist, a hostile regulator, a "
            "burned former customer, a short-seller analyst, security/legal skeptics."
        ),
    )
)

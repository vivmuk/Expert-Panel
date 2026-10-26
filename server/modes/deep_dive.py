"""Deep Dive — the default panel: blueprint, individual analyses, market
intelligence, synthesis with consensus and dissent."""
from .base import ModeSpec, register

register(
    ModeSpec(
        id="deep_dive",
        name="Deep Dive Panel",
        description="A bespoke panel of experts dissects your problem: blueprint, individual analyses, live market intelligence, and a synthesized report with consensus and dissent.",
        default_panel_size=20,
        result_kind="panel",
    )
)

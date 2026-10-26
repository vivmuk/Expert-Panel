"""Board Meeting — a simulated board debates a motion over rounds, then minutes
and a vote. Flow lives in pipeline/runner._board_flow."""
from .base import ModeSpec, register

register(
    ModeSpec(
        id="board_meeting",
        name="Board Meeting",
        description="A simulated board debates your motion across multiple rounds — opening positions, rebuttals, concessions — ending in minutes and a vote.",
        flow="board",
        default_panel_size=8,
        max_panel_size=12,
        include_market_intel=False,
        result_kind="board",
        defaults={"rounds": 3},
        mode_brief=(
            "Staff a board of directors: CEO-type, CFO-type, CTO-type, independent directors "
            "with governance experience, an activist investor, and relevant domain outsiders."
        ),
    )
)

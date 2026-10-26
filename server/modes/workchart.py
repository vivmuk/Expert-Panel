"""Work Chart — today vs. agent-era redesign, with breakthrough opportunities.
Flow lives in workchart/service.py."""
from .base import ModeSpec, register

register(
    ModeSpec(
        id="workchart",
        name="Work Chart",
        description="Map a process today vs. its AI-agent future: owners, agent functions, reusable agent assets, time/cost/FTE deltas — plus breakthrough redesign opportunities.",
        flow="workchart",
        include_market_intel=False,
        result_kind="workchart",
    )
)

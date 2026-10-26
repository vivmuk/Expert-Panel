"""Mode package.

Importing this module registers every mode. Each mode is a small file that owns
its spec, prompts and schemas; the runner and web app read the registry rather
than a hard-coded list, so adding a mode is an additive change.
"""
from .base import MODE_REGISTRY, ModeSpec, get_mode, insight_schema, modes, register

# Registration order is display order.
from . import deep_dive          # noqa: E402,F401
from . import red_team           # noqa: E402,F401
from . import quick_pulse        # noqa: E402,F401
from . import board_meeting      # noqa: E402,F401
from . import workchart          # noqa: E402,F401
from . import scenario_planning  # noqa: E402,F401
from . import due_diligence      # noqa: E402,F401
from . import ai_opportunity_scan  # noqa: E402,F401
from . import digital_twin       # noqa: E402,F401

__all__ = ["MODE_REGISTRY", "ModeSpec", "get_mode", "insight_schema", "modes", "register"]

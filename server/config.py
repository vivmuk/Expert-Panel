"""Central configuration, all driven by environment variables."""
import os


class Config:
    VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "")
    VENICE_BASE_URL = os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1")

    DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))

    # Pipeline guardrails
    DEFAULT_PANEL_SIZE = int(os.environ.get("DEFAULT_PANEL_SIZE", "20"))
    MAX_PANEL_SIZE = int(os.environ.get("MAX_PANEL_SIZE", "100"))
    PANEL_CONCURRENCY = int(os.environ.get("PANEL_CONCURRENCY", "8"))
    RUN_ANSWER_TIMEOUT_SECONDS = int(os.environ.get("RUN_ANSWER_TIMEOUT_SECONDS", "1800"))

    # Cost governance: abort a run whose actual spend exceeds this multiple of the estimate
    COST_CIRCUIT_BREAKER_MULTIPLIER = float(os.environ.get("COST_CIRCUIT_BREAKER_MULTIPLIER", "3.0"))

    # Model role defaults; every role is validated against live /models capabilities
    # at run time and falls back gracefully if an ID disappears from Venice.
    MODEL_ROLE_DEFAULTS = {
        "architect": os.environ.get("MODEL_ARCHITECT", "qwen3-235b-a22b-instruct-2507"),
        "persona_writer": os.environ.get("MODEL_PERSONA_WRITER", "qwen3-next-80b"),
        "expert": os.environ.get("MODEL_EXPERT", "qwen3-next-80b"),
        "market_agent": os.environ.get("MODEL_MARKET_AGENT", "zai-org-glm-5-2"),
        "synthesizer": os.environ.get("MODEL_SYNTHESIZER", "zai-org-glm-5-2"),
        "workchart": os.environ.get("MODEL_WORKCHART", "qwen3-235b-a22b-instruct-2507"),
        "breakthrough": os.environ.get("MODEL_BREAKTHROUGH", "qwen3-235b-a22b-thinking-2507"),
        "pulse": os.environ.get("MODEL_PULSE", "qwen3-4b"),
        "image": os.environ.get("MODEL_IMAGE", "qwen-image"),
    }


def require_api_key():
    if not Config.VENICE_API_KEY:
        raise RuntimeError("VENICE_API_KEY environment variable is required")

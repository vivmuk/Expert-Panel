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

    # Text roles share one default. Set MODEL_EXPERT, MODEL_WORKCHART, MODEL_JUDGE,
    # or the matching MODEL_* name to override a single role.
    DEFAULT_TEXT_MODEL = "deepseek-v4-1-flash-1017-uncensored"

    MODEL_ROLE_DEFAULTS = {
        "architect": os.environ.get("MODEL_ARCHITECT", DEFAULT_TEXT_MODEL),
        "persona_writer": os.environ.get("MODEL_PERSONA_WRITER", DEFAULT_TEXT_MODEL),
        "expert": os.environ.get("MODEL_EXPERT", DEFAULT_TEXT_MODEL),
        "market_agent": os.environ.get("MODEL_MARKET_AGENT", DEFAULT_TEXT_MODEL),
        "synthesizer": os.environ.get("MODEL_SYNTHESIZER", DEFAULT_TEXT_MODEL),
        "workchart": os.environ.get("MODEL_WORKCHART", DEFAULT_TEXT_MODEL),
        "breakthrough": os.environ.get("MODEL_BREAKTHROUGH", DEFAULT_TEXT_MODEL),
        "pulse": os.environ.get("MODEL_PULSE", DEFAULT_TEXT_MODEL),
        "judge": os.environ.get("MODEL_JUDGE", DEFAULT_TEXT_MODEL),
        "image": os.environ.get("MODEL_IMAGE", "qwen-image"),
    }


def require_api_key():
    if not os.environ.get("VENICE_API_KEY"):
        raise RuntimeError("VENICE_API_KEY environment variable is required")

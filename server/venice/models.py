"""Live model discovery and role→model resolution.

The catalog is refreshed from GET /models with a short TTL so newly released
Venice models appear automatically. Role resolution validates requested models
against capability flags and falls back to configured defaults, then to any
capable model, so a removed model ID never breaks a run.
"""
import logging
import threading
import time

from ..config import Config
from .client import get_client

logger = logging.getLogger(__name__)

CATALOG_TTL_SECONDS = 600

# Roles that require a specific capability flag on the model spec
ROLE_REQUIRED_CAPABILITIES = {
    "market_agent": "supportsWebSearch",
    "x_agent": "supportsXSearch",
}


class ModelCatalog:
    def __init__(self):
        self._lock = threading.Lock()
        self._models = []
        self._image_models = []
        self._fetched_at = 0.0
        self._last_failure_at = 0.0

    FAILURE_BACKOFF_SECONDS = 30

    def _refresh_if_stale(self):
        with self._lock:
            if time.time() - self._fetched_at < CATALOG_TTL_SECONDS and self._models:
                return
            if not self._models and time.time() - self._last_failure_at < self.FAILURE_BACKOFF_SECONDS:
                raise RuntimeError("Model catalog unavailable (recent refresh failure)")
            try:
                self._models = get_client().list_models(model_type="text")
                self._image_models = get_client().list_models(model_type="image")
                self._fetched_at = time.time()
                logger.info(
                    "Model catalog refreshed: %d text, %d image models",
                    len(self._models),
                    len(self._image_models),
                )
            except Exception:
                self._last_failure_at = time.time()
                logger.warning("Model catalog refresh failed; keeping stale data")
                if not self._models:
                    raise

    def text_models(self):
        self._refresh_if_stale()
        return list(self._models)

    def image_models(self):
        self._refresh_if_stale()
        return list(self._image_models)

    def spec(self, model_id):
        for m in self.text_models():
            if m.get("id") == model_id:
                return m
        return None

    def capabilities(self, model_id):
        spec = self.spec(model_id) or {}
        return (spec.get("model_spec") or {}).get("capabilities") or {}

    def pricing(self, model_id):
        spec = self.spec(model_id)
        if not spec:
            for m in self.image_models():
                if m.get("id") == model_id:
                    spec = m
                    break
        if not spec:
            return None
        pricing = (spec.get("model_spec") or {}).get("pricing") or {}
        input_price = (pricing.get("input") or {}).get("usd")
        output_price = (pricing.get("output") or {}).get("usd")
        if input_price is None and output_price is None:
            return None
        return {"input": float(input_price or 0.0), "output": float(output_price or 0.0)}

    def summary(self):
        """Frontend-friendly listing."""
        out = []
        for m in self.text_models():
            spec = m.get("model_spec") or {}
            caps = spec.get("capabilities") or {}
            pricing = self.pricing(m.get("id")) or {}
            out.append(
                {
                    "id": m.get("id"),
                    "name": spec.get("name") or m.get("id"),
                    "contextTokens": spec.get("availableContextTokens"),
                    "supportsWebSearch": bool(caps.get("supportsWebSearch")),
                    "supportsXSearch": bool(caps.get("supportsXSearch")),
                    "supportsReasoning": bool(caps.get("supportsReasoning")),
                    "supportsFunctionCalling": bool(caps.get("supportsFunctionCalling")),
                    "pricing": {
                        "inputPerMtok": pricing.get("input"),
                        "outputPerMtok": pricing.get("output"),
                    },
                }
            )
        return out

    def resolve_role(self, role, requested=None):
        """Pick a model for a pipeline role: requested > configured default >
        first capable model in the catalog."""
        required_cap = ROLE_REQUIRED_CAPABILITIES.get(role)
        candidates = [requested, Config.MODEL_ROLE_DEFAULTS.get(role)]
        for candidate in candidates:
            if not candidate:
                continue
            spec = self.spec(candidate)
            if spec is None:
                logger.warning("Model %r (role %s) not in live catalog; skipping", candidate, role)
                continue
            if required_cap and not self.capabilities(candidate).get(required_cap):
                logger.warning(
                    "Model %r lacks %s required for role %s; skipping", candidate, required_cap, role
                )
                continue
            return candidate
        for m in self.text_models():
            caps = (m.get("model_spec") or {}).get("capabilities") or {}
            if not required_cap or caps.get(required_cap):
                logger.warning("Role %s falling back to catalog model %r", role, m.get("id"))
                return m.get("id")
        raise RuntimeError(f"No Venice model available for role {role}")


_catalog = None


def get_catalog():
    global _catalog
    if _catalog is None:
        _catalog = ModelCatalog()
    return _catalog

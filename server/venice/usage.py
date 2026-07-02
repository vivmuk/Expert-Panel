"""Per-run token and cost accounting.

Pricing comes from the live /models response when available; the ledger keeps
one entry per API call so per-stage and per-model breakdowns are exact.
"""
import threading


class UsageLedger:
    def __init__(self, pricing_lookup=None):
        # pricing_lookup: callable(model_id) -> {"input": $/Mtok, "output": $/Mtok} or None
        self._pricing_lookup = pricing_lookup
        self._entries = []
        self._lock = threading.Lock()

    def record(self, stage, model, usage):
        prompt = int((usage or {}).get("prompt_tokens", 0) or 0)
        completion = int((usage or {}).get("completion_tokens", 0) or 0)
        cost = self._cost(model, prompt, completion)
        with self._lock:
            self._entries.append(
                {
                    "stage": stage,
                    "model": model,
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "cost_usd": cost,
                }
            )
        return cost

    def _cost(self, model, prompt_tokens, completion_tokens):
        pricing = self._pricing_lookup(model) if self._pricing_lookup else None
        if not pricing:
            return 0.0
        return (prompt_tokens / 1e6) * pricing.get("input", 0.0) + (
            completion_tokens / 1e6
        ) * pricing.get("output", 0.0)

    def totals(self):
        with self._lock:
            entries = list(self._entries)
        by_stage = {}
        for e in entries:
            s = by_stage.setdefault(
                e["stage"],
                {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0, "models": set()},
            )
            s["prompt_tokens"] += e["prompt_tokens"]
            s["completion_tokens"] += e["completion_tokens"]
            s["cost_usd"] += e["cost_usd"]
            s["calls"] += 1
            s["models"].add(e["model"])
        for s in by_stage.values():
            s["models"] = sorted(s["models"])
            s["cost_usd"] = round(s["cost_usd"], 6)
        return {
            "by_stage": by_stage,
            "total_prompt_tokens": sum(e["prompt_tokens"] for e in entries),
            "total_completion_tokens": sum(e["completion_tokens"] for e in entries),
            "total_cost_usd": round(sum(e["cost_usd"] for e in entries), 6),
            "total_calls": len(entries),
        }

    @property
    def total_cost_usd(self):
        with self._lock:
            return sum(e["cost_usd"] for e in self._entries)

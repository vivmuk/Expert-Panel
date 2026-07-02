"""Live smoke test of the Venice integration. Run before first deploy:

    VENICE_API_KEY=... python scripts/verify_venice.py

Checks: model discovery + capability flags, structured output, and real web
search with citations. Costs a fraction of a cent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.venice.client import VeniceClient  # noqa: E402

if not os.environ.get("VENICE_API_KEY"):
    sys.exit("Set VENICE_API_KEY first")

client = VeniceClient()

print("=== 1. Text models (capability flags drive role resolution) ===")
models = client.list_models(model_type="text")
print(f"{len(models)} models available")
for m in models:
    spec = m.get("model_spec") or {}
    caps = spec.get("capabilities") or {}
    print(
        f"  {m.get('id'):45s} ctx={spec.get('availableContextTokens')} "
        f"web={caps.get('supportsWebSearch')} x={caps.get('supportsXSearch')} "
        f"reasoning={caps.get('supportsReasoning')}"
    )

print("\n=== 2. Image models (branding generation) ===")
for m in client.list_models(model_type="image"):
    print(f"  {m.get('id')}")

print("\n=== 3. Structured output ===")
schema = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
small = models[0]["id"]
out = client.structured(
    small,
    [{"role": "user", "content": "One sentence: what does a management consultant do?"}],
    "Smoke",
    schema,
    max_completion_tokens=300,
)
print(f"  [{small}] {out.get('answer', out)}")

print("\n=== 4. Web search with citations ===")
web_model = next(
    (
        m["id"]
        for m in models
        if ((m.get("model_spec") or {}).get("capabilities") or {}).get("supportsWebSearch")
    ),
    None,
)
if not web_model:
    sys.exit("No web-search-capable model found — market intelligence will not work")
res = client.chat_search(
    web_model,
    [{"role": "user", "content": "What happened in enterprise AI agents this month? Cite sources."}],
    max_completion_tokens=600,
)
print(f"  [{web_model}] {res['content'][:300]}...")
print(f"  search results returned: {len(res['search_results'])}")
for r in res["search_results"][:5]:
    print(f"    - {json.dumps(r)[:140]}")

print("\nALL CHECKS PASSED — the platform is ready to run.")

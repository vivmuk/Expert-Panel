"""Run one full-depth demo. Usage: python scripts/run_demo.py maritime

Needs VENICE_API_KEY. Search goes through Venice Exa, so a separate Exa key is not required.
"""
import json
import os
import sys
import zipfile
from io import BytesIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.demo_pipeline import run_demo
from server.demo_schema import SLUGS
from server.exa_search import exa_search
from server.venice.client import VeniceClient


def complete(name, messages, schema, max_tokens):
    from server.config import Config

    model = Config.MODEL_ROLE_DEFAULTS["judge"] if name == "ChatDemoJudge" else Config.MODEL_ROLE_DEFAULTS["expert"]
    return VeniceClient().structured(model, messages, name, schema, temperature=0.3, max_completion_tokens=max_tokens)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SLUGS:
        print("Usage: python scripts/run_demo.py <maritime|keiki|orchid>", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("VENICE_API_KEY"):
        print("Set VENICE_API_KEY.", file=sys.stderr)
        sys.exit(1)
    slug = sys.argv[1]
    prompt_path = os.path.join(ROOT, "demos", "prompts", f"{slug}.md")
    with open(prompt_path, encoding="utf-8") as handle:
        problem = handle.read()
    demo = run_demo(slug, problem, complete, exa_search)
    out_dir = os.path.join(ROOT, "server", "static", "demos")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"{slug}.json")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(demo, handle, indent=2)
        handle.write("\n")
    zip_path = os.path.join(out_dir, f"{slug}.zip")
    _write_zip(zip_path, demo)
    print(json_path)
    print(zip_path)


def _write_zip(path, demo):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("problem.md", demo["problem"])
        archive.writestr("market.md", demo["market"]["summary"] + "\n\n" + "\n".join(
            f"- {item['title']} {item['url']}" for item in demo["market"]["citations"]
        ))
        archive.writestr("experts.json", json.dumps(demo["experts"], indent=2))
        archive.writestr("top5.json", json.dumps(demo["top5"], indent=2))
        for skill in demo["skills"]:
            slug = "".join(ch if ch.isalnum() else "-" for ch in skill.lower()).strip("-") or "skill"
            archive.writestr(f"skills/{slug}/SKILL.md", f"# {skill}\n")
        for item in demo["artifacts"]:
            archive.writestr(f"artifacts/{item['id']}.md", f"# {item['title']}\n")
    with open(path, "wb") as handle:
        handle.write(buf.getvalue())


if __name__ == "__main__":
    main()

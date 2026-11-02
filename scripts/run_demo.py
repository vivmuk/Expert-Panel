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

from server.artifact_doc import as_html, as_markdown
from server.demo_pipeline import run_demo
from server.demo_schema import SLUGS
from server.exa_search import exa_search
from server.venice.client import VeniceClient


def complete(name, messages, schema, max_tokens):
    from server.config import Config

    model = Config.MODEL_ROLE_DEFAULTS["judge"] if name == "ChatDemoJudge" else Config.MODEL_ROLE_DEFAULTS["expert"]
    if schema is None:  # long markdown documents: plain text, no JSON wrapping
        payload = {"model": model, "messages": messages, "temperature": 0.3, "max_completion_tokens": max_tokens,
                   "venice_parameters": {"disable_thinking": True, "include_venice_system_prompt": False}}
        resp = VeniceClient()._request("POST", "/chat/completions", json_body=payload)
        return {"markdown": (resp.json()["choices"][0]["message"].get("content") or "").strip()}
    for attempt in range(2):
        try:
            return VeniceClient().structured(model, messages, name, schema, temperature=0.3, max_completion_tokens=max(max_tokens * 2, 2000),
                venice_params={"disable_thinking": True},
            )
        except Exception as exc:  # one failed call should not sink a full run
            print(f"{name} attempt {attempt + 1} failed: {str(exc)[:200]}", file=sys.stderr)
            if "402" in str(exc):
                raise
    return {}


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
    kit_files = kit_file_map(demo)
    for rel, body in kit_files.items():
        full = os.path.join(out_dir, slug, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(body)
    demo["kit_files"]["paths"] = sorted(kit_files)
    json_path = os.path.join(out_dir, f"{slug}.json")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(demo, handle, indent=2)
        handle.write("\n")
    zip_path = os.path.join(out_dir, f"{slug}.zip")
    _write_zip(zip_path, demo)
    print(json_path)
    print(zip_path)


LABEL = "AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results."


def kit_file_map(demo):
    files = {}
    for skill in demo["kit_files"].get("skills") or []:
        desc = skill["description"].replace("\n", " ")
        body = f"---\nname: {skill['name']}\ndescription: {json.dumps(desc)}\n---\n\n> {LABEL}\n\n{skill['instructions'].strip()}\n"
        if skill.get("helper_filename"):
            if skill["helper_filename"] not in body:
                body += f"\n## Helper files\n\n- [{skill['helper_filename']}]({skill['helper_filename']})\n"
            files[f"kit/skills/{skill['name']}/{skill['helper_filename']}"] = skill["helper_content"].strip() + "\n"
        files[f"kit/skills/{skill['name']}/SKILL.md"] = body
    if demo["kit_files"].get("harness"):
        files["kit/harness.md"] = f"# {demo['company']} agent harness\n\n> {LABEL}\n\n" + demo["kit_files"]["harness"].strip() + "\n"
    return files


def _write_zip(path, demo):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", f"# {demo['company']} demo kit\n\n{demo['disclaimer']}\n")
        for rel, body in kit_file_map(demo).items():
            archive.writestr(rel, body)
        if demo.get("synthesis"):
            archive.writestr("synthesis.json", json.dumps(demo["synthesis"], indent=2))
        archive.writestr("debate.json", json.dumps(demo["debate"], indent=2))
        archive.writestr("problem.md", demo["problem"])
        archive.writestr("market.md", demo["market"]["summary"] + "\n\n" + "\n".join(
            f"- {item['title']} {item['url']}" for item in demo["market"]["citations"]
        ))
        archive.writestr("experts.json", json.dumps(demo["experts"], indent=2))
        archive.writestr("top5.json", json.dumps(demo["top5"], indent=2))
        for item in demo["artifacts"]:
            body = item.get("body") or item.get("title") or item["id"]
            archive.writestr(f"artifacts/{item['id']}.md", as_markdown(item.get("title") or item["id"], body, demo=True))
            archive.writestr(f"artifacts/{item['id']}.html", as_html(item.get("title") or item["id"], body, demo=True))
    with open(path, "wb") as handle:
        handle.write(buf.getvalue())


if __name__ == "__main__":
    main()

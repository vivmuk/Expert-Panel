import io
import json
import re
import zipfile

MAX_SKILLS = 10
MEDIUM_SKILLS = 6

VIV = {
    "blue": "#7fb2ff",
    "pink": "#c084fc",
    "surface": "#0d0f15",
    "ink": "#e9f0f5",
    "muted": "#a6adbd",
    "line": "#20242e",
    "display": "Playfair Display",
    "body": "DM Sans",
    "mono": "JetBrains Mono",
    "source": "https://designviv.up.railway.app",
}


def agent_steps(chart):
    steps = [step for step in (chart or {}).get("future") or [] if step.get("owner") in ("AI Agent", "Hybrid")]
    if steps:
        return steps
    summary = (chart or {}).get("summary") or "Draft the work."
    return [{"step": "Draft the agent steps", "task": summary, "owner": "Hybrid"}]


def plan_slots(tier, steps):
    steps = list(steps)
    if tier == "small":
        return [{"level": "task", "step": step} for step in steps[:MAX_SKILLS]]
    total = MEDIUM_SKILLS if tier == "medium" else MAX_SKILLS
    subs = steps[: max(0, total - 1)]
    return [{"level": "orchestrator", "step": None}] + [
        {"level": "workflow", "step": step} for step in subs
    ]


def pack_manifest(state):
    files = pack_files(state)
    return json.loads(files["skills/skills.json"])


def pack_files(state):
    chart = state.get("chart")
    brief = state.get("brief")
    tier = state.get("size")
    if not chart or not brief or tier not in ("small", "medium", "large"):
        raise ValueError("skill pack is not ready")
    steps = agent_steps(chart)
    slots = plan_slots(tier, steps)[:MAX_SKILLS]
    notes = state.get("skill_notes") or {}
    used = set()
    skills = []
    for slot in slots:
        if slot["level"] == "orchestrator":
            name = _slug("run the engagement", used)
            title = "Run the engagement"
            task = chart.get("summary") or "Run the agent-era process from the first step to the last."
            owner = "AI Agent"
        else:
            step = slot["step"]
            name = _slug(step["step"], used)
            title = step["step"]
            task = step["task"]
            owner = step["owner"]
        note = notes.get(name) or notes.get(title) or {}
        description = _description(note.get("description"), title, slot["level"])
        calls = [item["name"] for item in skills] if slot["level"] == "orchestrator" else []
        if slot["level"] == "orchestrator":
            calls = []
        skills.append(
            {
                "name": name,
                "title": title,
                "level": slot["level"],
                "task": task,
                "owner": owner,
                "description": description,
                "tools": _tools(note.get("tools"), title),
                "calls": calls,
            }
        )
    if skills and skills[0]["level"] == "orchestrator":
        skills[0]["calls"] = [item["name"] for item in skills[1:]]
    templates = _templates(state, steps)
    files = {}
    manifest_skills = []
    for skill in skills:
        folder = f"skills/{skill['name']}"
        files[f"{folder}/SKILL.md"] = _skill_md(skill, state)
        files[f"{folder}/references/research.md"] = _research_note(state)
        files[f"{folder}/scripts/render.py"] = _render_script()
        for path, body in templates.items():
            files[f"{folder}/{path}"] = body
        manifest_skills.append(
            {
                "name": skill["name"],
                "path": folder,
                "level": skill["level"],
                "description": skill["description"],
                "dependencies": {
                    "tools": skill["tools"],
                    "mcps": ["venice"],
                    "packages": [],
                    "skills": skill["calls"],
                },
            }
        )
    manifest = {
        "tier": tier,
        "style": "vivDesign",
        "styleSource": VIV["source"],
        "skills": manifest_skills,
    }
    if len(manifest["skills"]) > MAX_SKILLS:
        raise ValueError("skill cap")
    files["skills/skills.json"] = json.dumps(manifest, indent=2) + "\n"
    files["skills/README.md"] = _readme(state, manifest)
    return files


def build_pack_zip(state):
    return _zip(pack_files(state))


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, text in files.items():
            archive.writestr(path, text)
    return buf.getvalue()


def _description(given, title, level):
    text = " ".join(str(given or "").split())
    if "use this skill when" not in text.lower():
        if level == "orchestrator":
            text = f"Use this skill when the engagement starts and the sub-skills must run in playbook order. {text}".strip()
        else:
            text = f"Use this skill when playbook.md reaches {title}. {text}".strip()
    return text[:400]


def _tools(given, title):
    if isinstance(given, list) and given:
        cleaned = [str(item)[:40] for item in given[:4] if str(item).strip()]
        if cleaned:
            return cleaned
    if re.search(r"source|research|market", title, re.I):
        return ["web_search"]
    return []


def _slug(text, used):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "skill"
    name = base
    number = 2
    while name in used:
        name = f"{base}-{number}"
        number += 1
    used.add(name)
    return name


def _skill_md(skill, state):
    deps = skill["calls"] or ["none"]
    tools = skill["tools"] or ["none"]
    description = skill["description"].replace('"', "'")
    return "\n".join(
        [
            "---",
            f"name: {skill['name']}",
            f'description: "{description}"',
            "---",
            "",
            f"# {skill['title']}",
            "",
            f"Level is {skill['level']}. The owner is {skill['owner']}.",
            "",
            f"The task is {skill['task']}",
            "",
            "## Dependencies",
            "",
            f"Tools. {', '.join(tools)}.",
            "MCPs. venice.",
            "Packages. none.",
            f"Skills. {', '.join(deps)}.",
            "",
            "Read references/research.md before you draft.",
            "Fill templates/one-pager.html with scripts/render.py.",
            "Stop when the artifact is ready for the next owner.",
            "",
            f"Client problem. {state.get('problem') or ''}",
            "",
        ]
    )


def _research_note(state):
    brief = state.get("brief") or {}
    lines = ["# Research", "", brief.get("summary") or "", ""]
    for fact in (state.get("facts") or [])[:8]:
        lines.append(f"Fact. {fact}")
    lines.append("")
    for item in brief.get("citations") or []:
        lines.append(f"- {item.get('title')}. {item.get('url')}")
    lines.append("")
    return "\n".join(lines)


def _render_script():
    return "\n".join(
        [
            "import json",
            "import sys",
            "",
            "def fill(template, values):",
            "    for key, value in values.items():",
            "        template = template.replace('{{' + key + '}}', str(value))",
            "    return template",
            "",
            "def main():",
            "    values = json.load(sys.stdin)",
            "    path = sys.argv[1]",
            "    with open(path, encoding='utf-8') as handle:",
            "        sys.stdout.write(fill(handle.read(), values))",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]
    )


def _templates(state, steps):
    client = [item for item in (state.get("uploads") or []) if item.get("kind") == "template"]
    files = {
        "templates/one-pager.html": _viv_html("One pager", "{{headline}}", "{{body}}"),
        "templates/report.html": _viv_html("Report", "{{title}}", "{{body}}"),
        "templates/deck.html": _viv_html("Deck", "{{title}}", "{{slide}}"),
    }
    supported = [step["step"] for step in steps]
    notes = ["# Templates", "", "Default artifacts use the vivDesign blue and type colors.", ""]
    for item in client:
        safe = _slug(item["name"], set())
        ext = "html" if item["name"].lower().endswith((".html", ".htm")) else "md"
        work = _supported(item.get("text") or "", steps) or supported[:3]
        files[f"templates/client-{safe}.{ext}"] = item["text"]
        notes.append(f"{item['name']} supports {', '.join(work)}.")
    if not client:
        notes.append("No client template was uploaded. The three HTML files are the default artifacts.")
    files["templates/README.md"] = "\n".join(notes) + "\n"
    return files


def _supported(text, steps):
    lowered = text.lower()
    return [step["step"] for step in steps if step["step"].lower() in lowered]


def _viv_html(kind, title_token, body_token):
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{kind}</title>",
            "<style>",
            ":root {",
            f"  --viv-blue: {VIV['blue']};",
            f"  --viv-pink: {VIV['pink']};",
            f"  --viv-surface: {VIV['surface']};",
            f"  --viv-ink: {VIV['ink']};",
            f"  --viv-muted: {VIV['muted']};",
            "}",
            "body {",
            "  margin: 0;",
            f"  background: {VIV['surface']};",
            f"  color: {VIV['ink']};",
            f"  font-family: '{VIV['body']}', sans-serif;",
            "}",
            "main { max-width: 40rem; margin: 0 auto; padding: 3rem 1.5rem; }",
            "p.kicker {",
            f"  font-family: '{VIV['mono']}', monospace;",
            "  letter-spacing: 0.18em;",
            "  text-transform: uppercase;",
            "  color: var(--viv-blue);",
            "  font-size: 0.72rem;",
            "}",
            "h1 {",
            f"  font-family: '{VIV['display']}', serif;",
            "  font-weight: 500;",
            "  font-size: 3rem;",
            "  line-height: 1;",
            "  margin: 0.4rem 0 1rem;",
            "}",
            "h1 em { color: var(--viv-pink); font-style: italic; }",
            "article { font-size: 1.05rem; line-height: 1.6; }",
            f"footer {{ margin-top: 3rem; color: {VIV['muted']}; font-size: 0.8rem; }}",
            "</style>",
            "</head>",
            "<body>",
            "<main>",
            f"<p class=\"kicker\">{kind}</p>",
            f"<h1>{title_token}</h1>",
            f"<article>{body_token}</article>",
            f"<footer>Style from {VIV['source']}. Blue {VIV['blue']}. Type accent {VIV['pink']}.</footer>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _readme(state, manifest):
    lines = [
        "# Skill pack",
        "",
        f"Tier is {manifest['tier']}. {len(manifest['skills'])} skills. Cap is {MAX_SKILLS}.",
        "",
        "The harness reads this folder from CLAUDE.md and model-routing.md.",
        "Start with skills/skills.json. Call the skill whose description matches the playbook step.",
        "The orchestrator, when present, calls the other skills in order.",
        "",
        "Artifacts default to the vivDesign palette from " + VIV["source"] + ".",
        f"Blue is {VIV['blue']}. The type accent is {VIV['pink']}.",
        f"Display type is {VIV['display']}. Body type is {VIV['body']}. Mono is {VIV['mono']}.",
        "",
    ]
    for skill in manifest["skills"]:
        lines.append(f"- {skill['name']} ({skill['level']}). {skill['description']}")
    lines.append("")
    return "\n".join(lines)

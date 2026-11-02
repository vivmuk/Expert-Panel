import io
import re
import zipfile

from .chatjob import MATURITY, MATURITY_MEANING
from .config import Config
from .skillpack import pack_files


def build_kit_zip(state):
    files = kit_files(state)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, text in files.items():
            archive.writestr(path, text)
    return buf.getvalue()


def kit_files(state):
    chart = state.get("chart")
    if not chart or state.get("maturity") not in MATURITY:
        raise ValueError("chart missing")
    future = chart["future"]
    agent_steps = [step for step in future if step["owner"] != "Human"]
    if not agent_steps:
        agent_steps = [
            {"step": "Draft the agent steps", "task": chart["summary"], "owner": "Hybrid"}
        ]
    files = {
        "CLAUDE.md": _claude(state),
        "playbook.md": _playbook(state),
        "model-routing.md": _routing(state),
        "project-state-schema.md": _schema(state),
    }
    if state.get("pack") and state.get("brief") and state.get("size"):
        files.update(pack_files(state))
    else:
        used = set()
        for step in agent_steps:
            slug = _slug(step["step"], used)
            files[f"skills/{slug}/SKILL.md"] = _skill(step, state)
    for artifact_id, text in (state.get("artifacts") or {}).items():
        if isinstance(artifact_id, str) and isinstance(text, str) and text.strip():
            files[f"artifacts/{artifact_id}.md"] = text
    return files


def _slug(text, used):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "step"
    name = base
    number = 2
    while name in used:
        name = f"{base}-{number}"
        number += 1
    used.add(name)
    return name


def _claude(state):
    label = MATURITY[state["maturity"]]
    meaning = MATURITY_MEANING[state["maturity"]]
    return "\n".join(
        [
            f"# {state.get('service_line') or 'Engagement'}",
            "",
            "Read this file first. It is the operating rules for the agent that continues this job.",
            "",
            f"The problem is {state['problem']}",
            "",
            f"The team is {state['team'] or 'not specified'}.",
            f"The tools they use today are {state['tools'] or 'not specified'}.",
            f"AI maturity {state['maturity']} is {label}. {meaning}",
            "",
            "Rules.",
            "",
            "Read project-state-schema.md before you write state.",
            "Follow playbook.md in order.",
            "When skills/skills.json is present, call the skill whose description matches the step.",
            "A step owned by a Human stays with a person.",
            "A step owned by Hybrid stops for approval before anything leaves the team.",
            "Do not invent figures, quotes, or approvals the client did not give you.",
            "Keep notes in project-state.json.",
            "",
        ]
    )


def _playbook(state):
    lines = [
        f"# Playbook. {state.get('service_line') or 'Engagement'}",
        "",
        state["chart"]["summary"],
        "",
        "Run the steps in order.",
        "",
    ]
    for index, step in enumerate(state["chart"]["future"], start=1):
        lines.append(f"{index}. {step['step']}. The owner is {step['owner']}. {step['task']}")
    lines.append("")
    return "\n".join(lines)


def _routing(state):
    expert = Config.MODEL_ROLE_DEFAULTS["expert"]
    architect = Config.MODEL_ROLE_DEFAULTS["architect"]
    lines = [
        "# Model routing",
        "",
        f"Use {expert} for drafting, extraction, and the persona pass.",
        f"Use {architect} when the step needs a judgment a partner would sign.",
        "Keep each call short. This demo caps one answer at 1600 tokens.",
        "Do not send client material to a model that is not in this file.",
    ]
    if state.get("pack"):
        lines.append(
            f"The skill pack tier is {state.get('size')}. Read skills/skills.json before you pick a skill."
        )
    lines.append("")
    return "\n".join(lines)


def _schema(state):
    label = MATURITY[state["maturity"]]
    return "\n".join(
        [
            "# Project state",
            "",
            "Write `project-state.json` after each playbook step. Keep these fields.",
            "",
            "```json",
            "{",
            f'  "problem": {json_string(state["problem"])},',
            f'  "service_line": {json_string(state.get("service_line") or "")},',
            f'  "team": {json_string(state["team"])},',
            f'  "tools": {json_string(state["tools"])},',
            f'  "maturity": {state["maturity"]},',
            f'  "maturity_label": {json_string(label)},',
            '  "decisions": [],',
            '  "open_questions": []',
            "}",
            "```",
            "",
            "`decisions` is a list of short strings the client has accepted.",
            "`open_questions` is a list of facts you still need before the next Hybrid step.",
            "",
        ]
    )


def json_string(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _skill(step, state):
    label = MATURITY[state["maturity"]]
    return "\n".join(
        [
            f"# {step['step']}",
            "",
            f"The owner is {step['owner']}.",
            "",
            f"The task is {step['task']}",
            "",
            f"Use this skill when playbook.md reaches {step['step']}.",
            "",
            f"The client problem is {state['problem']}",
            f"The team is {state['team'] or 'not specified'}.",
            f"Tools today are {state['tools'] or 'not specified'}.",
            f"AI maturity {state['maturity']} is {label}.",
            "",
            "Do the task, then stop.",
            "If the owner is Hybrid, wait for a person to approve before anything is sent outside the team.",
            "",
        ]
    )

"""One generator for every catalog entry."""
import json

from .budget import TamperedState, commit_calls, reconcile_calls, sign_calls
from .catalog import STRATEGY_ARTIFACTS, by_id
from .chatjob import MAX_MODEL_CALLS, load_state, untrusted

FULL_EXTRA = 40
SCHEMA = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
    "additionalProperties": False,
}

_FORMAT = {
    "markdown": "Write prose under each section heading.",
    "table": "Under each section, include a markdown table. A reader should be able to copy the rows into a spreadsheet.",
    "mermaid": "Include one fenced mermaid diagram. Use a gantt chart for a workplan, a flowchart for a process, and a tree for an issue, hypothesis, or KPI tree.",
}


class ArtifactError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def generate_artifact(raw_state, artifact_id, complete):
    entry = by_id(artifact_id)
    if entry is None:
        raise ArtifactError("unknown", "Unknown artifact.")
    raw = raw_state if isinstance(raw_state, dict) else {}
    state = load_state(raw)
    try:
        state["calls"] = reconcile_calls(state["chat_id"], raw.get("calls"), raw.get("sig"))
    except TamperedState as exc:
        raise ArtifactError("tamper", "The job state did not match its signature.") from exc
    have = state.get("artifacts") or {}
    limit = None if state.get("depth") == "full" else STRATEGY_ARTIFACTS
    if limit is not None and artifact_id not in have and len(have) >= limit:
        raise ArtifactError(
            "limit",
            "The Strategy engagement includes 5 catalog artifacts. Harness Build covers the full catalog.",
        )
    extra = FULL_EXTRA if state.get("depth") == "full" else STRATEGY_ARTIFACTS
    if state["calls"] >= MAX_MODEL_CALLS + extra:
        raise ArtifactError("budget", "This job has used its model-call budget.")
    data = complete(
        "ChatArtifact",
        [
            {"role": "system", "content": _system(entry)},
            {"role": "user", "content": _user(entry, state)},
        ],
        SCHEMA,
        1600,
    )
    markdown = ""
    if isinstance(data, dict):
        markdown = str(data.get("markdown") or "").strip()
    if not markdown:
        raise ArtifactError("incomplete", "The model returned an empty artifact.")
    state["calls"] += 1
    have = dict(have)
    have[artifact_id] = markdown[:20000]
    state["artifacts"] = have
    commit_calls(state["chat_id"], state["calls"])
    sig = sign_calls(state["chat_id"], state["calls"])
    if sig:
        state["sig"] = sig
    return {"artifact_id": artifact_id, "markdown": have[artifact_id], "state": state}


def _system(entry):
    sections = "\n".join(f"- {name}" for name in entry["sections"])
    return "\n".join(
        [
            "You write one consulting artifact as markdown.",
            "Use only facts in the engagement data and the cited sources.",
            "If a number is not in that data, write the word assumption next to it.",
            "Do not invent figures, quotes, or sources.",
            f"Title: {entry['title']}.",
            f"Purpose: {entry['purpose']}",
            "Use these section headings, in order, as level-2 headings:",
            sections,
            _FORMAT[entry["format"]],
            'Return JSON with one field, markdown, containing the document.',
        ]
    )


def _user(entry, state):
    payload = {}
    for key in entry["inputs"]:
        payload[key] = state.get(key)
    citations = []
    brief = state.get("brief") or {}
    for item in brief.get("citations") or []:
        if isinstance(item, dict) and item.get("url"):
            citations.append({"title": item.get("title") or item["url"], "url": item["url"], "note": item.get("note") or ""})
    return "\n\n".join(
        [
            untrusted("Engagement data", json.dumps(payload, ensure_ascii=True, default=str)[:12000]),
            untrusted("Research citations", json.dumps(citations, ensure_ascii=True)[:6000]),
            "Sections: " + ", ".join(entry["sections"]),
        ]
    )

import logging
import re
import uuid

logger = logging.getLogger(__name__)

MAX_MODEL_CALLS = 4
MAX_OUTPUT_TOKENS = 1600

MATURITY = {
    1: "Invoice-led",
    2: "Pilot-led",
    3: "Hybrid",
    4: "Machine-led",
}

MATURITY_MEANING = {
    1: "People do the work. AI is a side tool.",
    2: "One workflow is in a pilot.",
    3: "Agents draft and humans approve, as the normal path.",
    4: "Agents run the process. Humans handle exceptions.",
}

PHASES = (
    "ask_problem",
    "ask_context",
    "ask_maturity",
    "panel",
    "red_team",
    "blueprint",
    "done",
)

WELCOME = (
    "AI Partner takes one consulting job from the first question to a harness kit. "
    "Name the job, in any service line. "
    "Examples include market entry for a medtech device into Germany, "
    "pricing for a B2B analytics product, "
    "finance close for a 40-person company, "
    "and a Medical Affairs response for a new label."
)

ASK_CONTEXT = "Who is on the team, and which tools do they use today?"

ASK_MATURITY = (
    "Score the team's AI maturity from 1 to 4. "
    "1 is Invoice-led. "
    "2 is Pilot-led. "
    "3 is Hybrid. "
    "4 is Machine-led. "
    "Add the words red team if you want an adversarial pass."
)

BUDGET_REPLY = (
    "This job hit the demo budget of 4 model calls. "
    "Start a new chat to take another job."
)

INCOMPLETE_REPLY = (
    "The model returned an incomplete answer. "
    "Your earlier answers are still here. Send the message again."
)

DONE_REPLY = "This job is finished. Start a new chat to take another."

_LABELS = (
    (1, ("invoice-led", "invoice led")),
    (2, ("pilot-led", "pilot led")),
    (3, ("hybrid",)),
    (4, ("machine-led", "machine led")),
)


def _str(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _chat_id(value):
    if isinstance(value, str):
        safe = re.sub(r"[^A-Za-z0-9_-]", "", value)[:40]
        if safe:
            return safe
    return uuid.uuid4().hex[:16]


def fresh_state(chat_id):
    return {
        "chat_id": chat_id,
        "phase": "ask_problem",
        "problem": "",
        "team": "",
        "tools": "",
        "maturity": None,
        "red_team": False,
        "service_line": "",
        "panel": None,
        "attacks": None,
        "chart": None,
        "calls": 0,
        "memories": "",
    }


def normalize_panel(raw):
    if not isinstance(raw, dict):
        return None
    personas = []
    for item in (raw.get("personas") or [])[:4]:
        if not isinstance(item, dict):
            continue
        persona = {
            "name": _str(item.get("name"), 80),
            "title": _str(item.get("title"), 80),
            "insight": _str(item.get("insight"), 400),
            "recommendation": _str(item.get("recommendation"), 300),
        }
        if all(persona.values()):
            personas.append(persona)
    if len(personas) != 4:
        return None
    consensus = _str(raw.get("consensus"), 500)
    if not consensus:
        return None

    def bullets(key):
        found = []
        for item in (raw.get(key) or [])[:3]:
            text = _str(item, 200)
            if text:
                found.append(text)
        return found

    now, nxt, later = bullets("now"), bullets("next"), bullets("later")
    if not (now and nxt and later):
        return None
    return {
        "service_line": _str(raw.get("service_line"), 120) or "Consulting",
        "personas": personas,
        "consensus": consensus,
        "dissent": _str(raw.get("dissent"), 400),
        "now": now,
        "next": nxt,
        "later": later,
    }


def normalize_attacks(raw):
    if not isinstance(raw, dict):
        return None
    top = _str(raw.get("top_risk"), 200)
    attacks = []
    for item in (raw.get("attacks") or [])[:3]:
        if not isinstance(item, dict):
            continue
        attack = {
            "threat": _str(item.get("threat"), 200),
            "why": _str(item.get("why"), 300),
            "mitigation": _str(item.get("mitigation"), 300),
        }
        if attack["threat"] and attack["mitigation"]:
            attacks.append(attack)
    if not top or len(attacks) < 3:
        return None
    return {"top_risk": top, "attacks": attacks}


def _steps(raw, allowed, fallback):
    steps = []
    if not isinstance(raw, list):
        return steps
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        step = _str(item.get("step"), 80)
        task = _str(item.get("task"), 240)
        owner = item.get("owner")
        if owner not in allowed:
            owner = fallback
        if step and task:
            steps.append({"step": step, "task": task, "owner": owner})
    return steps


def normalize_chart(raw):
    if not isinstance(raw, dict):
        return None
    current = _steps(raw.get("current"), ("Human",), "Human")
    future = _steps(raw.get("future"), ("Human", "AI Agent", "Hybrid"), "Hybrid")
    summary = _str(raw.get("summary"), 400)
    if len(current) < 2 or len(future) < 2 or not summary:
        return None
    return {"current": current, "future": future, "summary": summary}


def _rewind(state, phase):
    working = phase in ("panel", "red_team", "blueprint", "done")
    if working and (not state["problem"] or state["maturity"] not in MATURITY):
        return "ask_maturity" if state["problem"] else "ask_problem"
    if phase in ("red_team", "blueprint", "done") and not state["panel"]:
        return "panel"
    if phase in ("blueprint", "done") and state["red_team"] and not state["attacks"]:
        return "red_team"
    if phase == "red_team" and not state["red_team"]:
        return "done" if state["chart"] else "blueprint"
    if phase == "done" and not state["chart"]:
        return "blueprint"
    if phase == "blueprint" and state["chart"]:
        return "done"
    return phase


def load_state(raw):
    raw = raw if isinstance(raw, dict) else {}
    state = fresh_state(_chat_id(raw.get("chat_id")))
    state["problem"] = _str(raw.get("problem"), 4000)
    state["team"] = _str(raw.get("team"), 1000)
    state["tools"] = _str(raw.get("tools"), 1000)
    maturity = raw.get("maturity")
    if isinstance(maturity, str) and maturity.isdigit():
        maturity = int(maturity)
    if maturity in MATURITY:
        state["maturity"] = maturity
    state["red_team"] = bool(raw.get("red_team"))
    calls = raw.get("calls")
    if isinstance(calls, int) and not isinstance(calls, bool) and calls > 0:
        state["calls"] = min(calls, MAX_MODEL_CALLS)
    state["memories"] = _str(raw.get("memories"), 800)
    state["service_line"] = _str(raw.get("service_line"), 120)
    panel = normalize_panel(raw.get("panel"))
    if panel:
        state["panel"] = panel
        state["service_line"] = state["service_line"] or panel["service_line"]
    attacks = normalize_attacks(raw.get("attacks"))
    if attacks:
        state["attacks"] = attacks
    chart = normalize_chart(raw.get("chart"))
    if chart:
        state["chart"] = chart
    phase = raw.get("phase")
    state["phase"] = _rewind(state, phase if phase in PHASES else "ask_problem")
    return state


def parse_maturity(text, phase):
    lowered = " ".join(text.lower().split())
    if phase == "ask_maturity":
        matched = re.match(r"^([1-4])\b", lowered)
        if matched:
            return int(matched.group(1))
        for score, phrases in _LABELS:
            if any(phrase in lowered for phrase in phrases):
                return score
        return None
    matched = re.search(r"\bmaturity\b.{0,24}?\b([1-4])\b", lowered)
    if matched:
        return int(matched.group(1))
    if "maturity" not in lowered:
        return None
    for score, phrases in _LABELS:
        if any(phrase in lowered for phrase in phrases):
            return score
    return None


def _has_context(text):
    has_team = re.search(r"\bteam\b", text, re.I)
    has_tools = re.search(r"\btools?\b", text, re.I) or re.search(r"\busing\b", text, re.I)
    return bool(has_team and has_tools)


def _cut_tail(value):
    matched = re.search(r"\btools?\s*:|\bmaturity\b", value, flags=re.I)
    if matched:
        value = value[: matched.start()]
    return value.strip(" .;")


def split_team_tools(text):
    team_match = re.search(r"\bteam\s*:\s*(.+)", text, flags=re.I)
    tool_match = re.search(r"\btools?\s*:\s*(.+)", text, flags=re.I)
    if team_match or tool_match:
        team = _cut_tail(team_match.group(1)) if team_match else ""
        tools = _cut_tail(tool_match.group(1)) if tool_match else ""
        return team, tools
    parts = re.split(r"\busing\b", text, maxsplit=1, flags=re.I)
    if len(parts) == 2 and parts[1].strip():
        return parts[0].strip(" .;"), _cut_tail(parts[1])
    return text.strip(), ""


def wants_red_team(text):
    lowered = text.lower()
    return "red team" in lowered or "red-team" in lowered


def _pack(reply, state, nxt, error=None):
    return {"reply": reply, "state": state, "next": nxt, "error": error}


def _remember(remember, state):
    if remember is None:
        return
    try:
        remember(state["chat_id"], memory_text(state))
    except Exception:
        logger.info("engagement memory write failed for %s", state["chat_id"])


def memory_text(state):
    label = MATURITY.get(state.get("maturity"), "")
    consensus = ""
    if state.get("panel"):
        consensus = state["panel"]["consensus"]
    return (
        f"Problem: {state['problem']}\n"
        f"Team: {state['team']}\n"
        f"Tools: {state['tools']}\n"
        f"Maturity: {state.get('maturity')} {label}\n"
        f"Service line: {state.get('service_line', '')}\n"
        f"Consensus: {consensus}"
    )


def handle_turn(raw_state, message, complete, recall=None, remember=None):
    """Advance one job. `complete(name, messages, schema, max_tokens)` calls the model."""
    state = load_state(raw_state)
    message = _str(message or "", 8000)
    if state["phase"] == "done":
        if len(message) > 15:
            restarted = fresh_state(state["chat_id"])
            return handle_turn(restarted, message, complete, recall, remember)
        return _pack(DONE_REPLY, state, None)
    if state["phase"] in ("ask_problem", "ask_context", "ask_maturity"):
        reply, state = _intake(state, message)
        if state["phase"] != "panel":
            return _pack(reply, state, None)
        return _run_work(state, complete, recall, remember)
    return _run_work(state, complete, recall, remember)


def _intake(state, message):
    phase = state["phase"]
    if phase == "ask_problem":
        if not message or re.fullmatch(r"[1-4]", message):
            return WELCOME, state
        state["problem"] = message
        state["red_team"] = wants_red_team(message)
        maturity = parse_maturity(message, phase)
        if _has_context(message):
            team, tools = split_team_tools(message)
            state["team"] = team[:1000]
            state["tools"] = tools[:1000]
            if maturity:
                state["maturity"] = maturity
                state["phase"] = "panel"
                return "", state
            state["phase"] = "ask_maturity"
            return ASK_MATURITY, state
        state["phase"] = "ask_context"
        return ASK_CONTEXT, state

    if phase == "ask_context":
        if not message:
            return ASK_CONTEXT, state
        team, tools = split_team_tools(message)
        state["team"] = (team or message)[:1000]
        state["tools"] = tools[:1000]
        state["red_team"] = state["red_team"] or wants_red_team(message)
        maturity = parse_maturity(message, phase)
        if maturity:
            state["maturity"] = maturity
            state["phase"] = "panel"
            return "", state
        state["phase"] = "ask_maturity"
        return ASK_MATURITY, state

    if not message:
        return ASK_MATURITY, state
    state["red_team"] = state["red_team"] or wants_red_team(message)
    maturity = parse_maturity(message, phase)
    if not maturity:
        return ASK_MATURITY, state
    state["maturity"] = maturity
    state["phase"] = "panel"
    return "", state


def _run_work(state, complete, recall, remember):
    if state["calls"] >= MAX_MODEL_CALLS:
        return _pack(
            BUDGET_REPLY,
            state,
            None,
            {"code": "budget", "message": BUDGET_REPLY},
        )
    phase = state["phase"]
    if phase == "panel":
        return _panel(state, complete, recall, remember)
    if phase == "red_team":
        return _red_team(state, complete)
    return _blueprint(state, complete, remember)


def _brief(state):
    label = MATURITY[state["maturity"]]
    meaning = MATURITY_MEANING[state["maturity"]]
    tools = state["tools"] or "not specified"
    lines = [
        f"Problem: {state['problem']}",
        f"Team: {state['team'] or 'not specified'}",
        f"Tools today: {tools}",
        f"AI maturity {state['maturity']} is {label}. {meaning}",
    ]
    if state.get("memories"):
        lines.append(f"Prior context from this client: {state['memories']}")
    return "\n".join(lines)


def _panel(state, complete, recall, remember):
    if recall is not None:
        try:
            state["memories"] = _str(recall(state["chat_id"], state["problem"]) or "", 800)
        except Exception:
            logger.info("engagement memory read failed for %s", state["chat_id"])
            state["memories"] = ""
    system = (
        "You staff a four-person expert panel for one consulting job. "
        "The service line may be any practice a large firm sells. Name it in a few words. "
        "Each persona speaks only from that person's background, with one insight and one recommendation. "
        "Then give the consensus, the main dissent, and now, next, and later actions. "
        "Do not invent statistics or quotes."
    )
    data = complete(
        "ChatPanel",
        [{"role": "system", "content": system}, {"role": "user", "content": _brief(state)}],
        PANEL_SCHEMA,
        MAX_OUTPUT_TOKENS,
    )
    state["calls"] += 1
    panel = normalize_panel(data)
    if not panel:
        return _pack(INCOMPLETE_REPLY, state, None, {"code": "incomplete", "message": INCOMPLETE_REPLY})
    state["panel"] = panel
    state["service_line"] = panel["service_line"]
    _remember(remember, state)
    nxt = "red_team" if state["red_team"] else "blueprint"
    state["phase"] = nxt
    return _pack(_format_panel(panel), state, nxt)


def _format_panel(panel):
    lines = [f"Four-person panel on {panel['service_line']}."]
    for persona in panel["personas"]:
        lines.append(f"{persona['name']}, {persona['title']}. {persona['insight']}")
    lines.append(panel["consensus"])
    if panel["dissent"]:
        lines.append(panel["dissent"])
    return "\n\n".join(lines)


def _red_team(state, complete):
    system = (
        "You are a red team. Attack the plan. Do not praise it. "
        "Name the single top risk and three ways the plan fails. "
        "Each attack needs a mitigation the client can carry out."
    )
    user = _brief(state) + "\n\nPlan under attack: " + state["panel"]["consensus"]
    data = complete(
        "ChatRedTeam",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        RED_TEAM_SCHEMA,
        900,
    )
    state["calls"] += 1
    attacks = normalize_attacks(data)
    if not attacks:
        return _pack(INCOMPLETE_REPLY, state, None, {"code": "incomplete", "message": INCOMPLETE_REPLY})
    state["attacks"] = attacks
    state["phase"] = "blueprint"
    lines = [f"Red team. The top risk is {attacks['top_risk']}."]
    for attack in attacks["attacks"]:
        lines.append(f"{attack['threat']}. {attack['mitigation']}")
    return _pack("\n\n".join(lines), state, "blueprint")


def _blueprint(state, complete, remember):
    system = (
        "You map one consulting process twice. "
        "Today every owner is Human. "
        "In the agent era each owner is Human, AI Agent, or Hybrid. "
        "Human means judgment, a relationship, or accountability. "
        "AI Agent means the step can run without a person. "
        "Hybrid means an agent drafts and a person approves. "
        "Use 3 to 6 steps on each side. Do not ask questions."
    )
    user = _brief(state) + "\n\nPanel consensus: " + state["panel"]["consensus"]
    data = complete(
        "ChatChart",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        CHART_SCHEMA,
        MAX_OUTPUT_TOKENS,
    )
    state["calls"] += 1
    chart = normalize_chart(data)
    if not chart:
        return _pack(INCOMPLETE_REPLY, state, None, {"code": "incomplete", "message": INCOMPLETE_REPLY})
    state["chart"] = chart
    state["phase"] = "done"
    _remember(remember, state)
    return _pack(final_text(state), state, None)


def _chart_block(title, steps):
    lines = [title]
    for step in steps:
        lines.append(f"{step['step']}. Owner {step['owner']}. {step['task']}")
    return "\n".join(lines)


def final_text(state):
    import os

    chart = state["chart"]
    future = chart["future"]
    handed = [step for step in future if step["owner"] != "Human"]
    label = MATURITY[state["maturity"]]
    lines = [
        f"Job. {state['service_line']}.",
        f"Maturity {state['maturity']} is {label}.",
        state["panel"]["consensus"],
        chart["summary"],
        _chart_block("Today.", chart["current"]),
        _chart_block("Agent era.", future),
        (
            f"Work chart. {len(chart['current'])} steps today. "
            f"{len(future)} steps in the agent era. "
            f"{len(handed)} of those are AI Agent or Hybrid."
        ),
        (
            "The harness kit contains CLAUDE.md, playbook.md, model-routing.md, "
            "project-state-schema.md, and one SKILL.md for each agent step."
        ),
        "Download the report at /api/chat/report and the kit at /api/chat/kit. POST this job state.",
    ]
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        lines.append(f"On this host those paths are {base}/api/chat/report and {base}/api/chat/kit.")
    return "\n\n".join(lines)


def render_report(state):
    state = load_state(state)
    if not state.get("chart") or not state.get("panel") or state.get("maturity") not in MATURITY:
        raise ValueError("not ready")
    label = MATURITY[state["maturity"]]
    lines = [
        f"# {state['service_line']}",
        "",
        state["problem"],
        "",
        f"Team: {state['team'] or 'not specified'}",
        "",
        f"Tools today: {state['tools'] or 'not specified'}",
        "",
        f"AI maturity {state['maturity']} is {label}. {MATURITY_MEANING[state['maturity']]}",
        "",
        "## Panel",
        "",
        state["panel"]["consensus"],
        "",
    ]
    if state["panel"]["dissent"]:
        lines.extend(["Dissent. " + state["panel"]["dissent"], ""])
    for persona in state["panel"]["personas"]:
        lines.extend(
            [
                f"### {persona['name']}, {persona['title']}",
                "",
                persona["insight"],
                "",
                persona["recommendation"],
                "",
            ]
        )
    lines.extend(["Now. " + " ".join(state["panel"]["now"]), ""])
    lines.extend(["Next. " + " ".join(state["panel"]["next"]), ""])
    lines.extend(["Later. " + " ".join(state["panel"]["later"]), ""])
    if state.get("attacks"):
        lines.extend(["## Red team", "", f"Top risk. {state['attacks']['top_risk']}", ""])
        for attack in state["attacks"]["attacks"]:
            lines.extend([f"### {attack['threat']}", "", attack["why"], "", attack["mitigation"], ""])
    chart = state["chart"]
    lines.extend(["## Work chart", "", chart["summary"], "", "### Today", ""])
    for step in chart["current"]:
        lines.append(f"- {step['step']}. Owner {step['owner']}. {step['task']}")
    lines.extend(["", "### Agent era", ""])
    for step in chart["future"]:
        lines.append(f"- {step['step']}. Owner {step['owner']}. {step['task']}")
    lines.append("")
    return "\n".join(lines)


def _schema(properties, required):
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_PERSONA = _schema(
    {
        "name": {"type": "string"},
        "title": {"type": "string"},
        "insight": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    ["name", "title", "insight", "recommendation"],
)

_STRINGS = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}

PANEL_SCHEMA = _schema(
    {
        "service_line": {"type": "string"},
        "personas": {"type": "array", "items": _PERSONA, "minItems": 4, "maxItems": 4},
        "consensus": {"type": "string"},
        "dissent": {"type": "string"},
        "now": _STRINGS,
        "next": _STRINGS,
        "later": _STRINGS,
    },
    ["service_line", "personas", "consensus", "dissent", "now", "next", "later"],
)

_ATTACK = _schema(
    {"threat": {"type": "string"}, "why": {"type": "string"}, "mitigation": {"type": "string"}},
    ["threat", "why", "mitigation"],
)

RED_TEAM_SCHEMA = _schema(
    {
        "top_risk": {"type": "string"},
        "attacks": {"type": "array", "items": _ATTACK, "minItems": 3, "maxItems": 3},
    },
    ["top_risk", "attacks"],
)

_STEP = _schema(
    {
        "step": {"type": "string"},
        "task": {"type": "string"},
        "owner": {"type": "string", "enum": ["Human", "AI Agent", "Hybrid"]},
    },
    ["step", "task", "owner"],
)

_STEP_LIST = {"type": "array", "items": _STEP, "minItems": 3, "maxItems": 6}

CHART_SCHEMA = _schema(
    {"current": _STEP_LIST, "future": _STEP_LIST, "summary": {"type": "string"}},
    ["current", "future", "summary"],
)

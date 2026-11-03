"""Consulting artifacts, grouped by the nine tasks in the thesis draft."""

TASKS = (
    ("Data gathering and market research", 10),
    ("Benchmarking and comps", 10),
    ("Financial modeling", 9),
    ("Deck and exhibit production", 9),
    ("Synthesis and recommendations", 9),
    ("Expert interviews", 5),
    ("Org design and change", 4),
    ("Program management", 3),
    ("Political cover and decision validation", 2),
)

INPUTS = (
    "problem",
    "team",
    "tools",
    "maturity",
    "service_line",
    "size",
    "panel",
    "chart",
    "brief",
    "sources",
    "facts",
    "attacks",
)

FORMATS = ("markdown", "table", "mermaid")
STRATEGY_ARTIFACTS = 5

_CORE = ("problem", "team", "tools", "maturity", "service_line")


def _entry(artifact_id, title, group, purpose, sections, fmt, inputs):
    return {
        "id": artifact_id,
        "title": title,
        "group": group,
        "purpose": purpose,
        "sections": list(sections),
        "format": fmt,
        "inputs": list(inputs),
    }


def _rows(*names):
    return _CORE + names


CATALOG = (
    _entry(
        "research-brief",
        "Research brief",
        "Data gathering and market research",
        "The cited brief already produced for this job, restated with its sources.",
        ("Summary", "Sources", "Facts from the client"),
        "markdown",
        _rows("brief", "sources", "facts"),
    ),
    _entry(
        "market-sizing",
        "Market sizing",
        "Data gathering and market research",
        "TAM, SAM, and SOM with each assumption written out.",
        ("TAM", "SAM", "SOM", "Assumptions", "Sources"),
        "table",
        _rows("brief", "sources", "facts"),
    ),
    _entry(
        "competitive-landscape",
        "Competitive landscape",
        "Data gathering and market research",
        "A comparison of competitors named in the research or by the client.",
        ("Competitors", "Comparison", "Sources"),
        "table",
        _rows("brief", "sources"),
    ),
    _entry(
        "customer-segmentation",
        "Customer segmentation",
        "Data gathering and market research",
        "Segments of buyers or users, with the basis for each cut.",
        ("Segments", "Needs", "Assumptions"),
        "table",
        _rows("brief", "panel"),
    ),
    _entry(
        "due-diligence",
        "Due-diligence checklist",
        "Data gathering and market research",
        "A checklist of questions and documents for a target or a market entry.",
        ("Commercial", "Operations", "Financial", "Open questions"),
        "markdown",
        _rows("brief", "facts"),
    ),
    _entry(
        "vendor-evaluation",
        "Vendor and tool evaluation",
        "Benchmarking and comps",
        "A matrix of tools or vendors against the criteria the team cares about.",
        ("Criteria", "Options", "Score", "Assumptions"),
        "table",
        _rows("tools", "facts"),
    ),
    _entry(
        "cost-reduction",
        "Cost-reduction opportunity log",
        "Benchmarking and comps",
        "A log of cost opportunities, each marked as a finding or an assumption.",
        ("Opportunities", "Evidence", "Assumptions"),
        "table",
        _rows("brief", "chart", "facts"),
    ),
    _entry(
        "pricing-analysis",
        "Pricing analysis",
        "Financial modeling",
        "How price is set today and the options, with formulas shown as assumptions when the data is missing.",
        ("Current price", "Options", "Formulas", "Assumptions"),
        "table",
        _rows("brief", "facts"),
    ),
    _entry(
        "business-case",
        "Business case and ROI",
        "Financial modeling",
        "Costs, benefits, and the ROI formulas. Missing numbers are labeled assumption.",
        ("Costs", "Benefits", "Formulas", "Payback", "Assumptions"),
        "markdown",
        _rows("brief", "chart", "facts"),
    ),
    _entry(
        "board-one-pager",
        "Board one-pager",
        "Deck and exhibit production",
        "One page a board can read: the decision, the evidence, and the ask.",
        ("Decision", "Evidence", "Ask", "Risks"),
        "markdown",
        _rows("panel", "brief", "chart"),
    ),
    _entry(
        "issue-tree",
        "Issue tree",
        "Synthesis and recommendations",
        "The question broken into issues, as a mermaid tree.",
        ("Question", "Issues", "Diagram"),
        "mermaid",
        _rows("panel"),
    ),
    _entry(
        "hypothesis-tree",
        "Hypothesis tree",
        "Synthesis and recommendations",
        "The working hypotheses and what would confirm or drop each one.",
        ("Hypotheses", "Tests", "Diagram"),
        "mermaid",
        _rows("panel", "brief"),
    ),
    _entry(
        "exec-memo",
        "Exec summary memo",
        "Synthesis and recommendations",
        "A pyramid memo: the answer first, then the supporting points.",
        ("Answer", "Support", "Risks", "Next step"),
        "markdown",
        _rows("panel", "brief", "chart"),
    ),
    _entry(
        "interview-guide",
        "Interview guide",
        "Expert interviews",
        "Questions for the people who do the work, tied to the issues.",
        ("Who to interview", "Questions", "What to listen for"),
        "markdown",
        _rows("panel", "team"),
    ),
    _entry(
        "stakeholder-map",
        "Stakeholder map",
        "Expert interviews",
        "Who decides, who is affected, and what each person needs.",
        ("People", "Role in the decision", "What they need"),
        "table",
        _rows("team", "panel"),
    ),
    _entry(
        "workshop",
        "Workshop agenda",
        "Expert interviews",
        "A facilitation agenda for one working session.",
        ("Purpose", "Agenda", "Materials", "Decisions to leave with"),
        "markdown",
        _rows("panel", "chart"),
    ),
    _entry(
        "current-process",
        "Current-state process map",
        "Org design and change",
        "The work as it is done today, as a mermaid flowchart.",
        ("Steps", "Diagram", "Pain points"),
        "mermaid",
        _rows("chart"),
    ),
    _entry(
        "future-process",
        "Future-state process map",
        "Org design and change",
        "The agent-era process, as a mermaid flowchart.",
        ("Steps", "Diagram", "What stays with a person"),
        "mermaid",
        _rows("chart"),
    ),
    _entry(
        "operating-model",
        "Operating model",
        "Org design and change",
        "Who owns the work after the change, across people and agents.",
        ("Work", "Owners", "Cadence", "Open decisions"),
        "markdown",
        _rows("chart", "team", "maturity"),
    ),
    _entry(
        "change-plan",
        "Change and communications plan",
        "Org design and change",
        "What each group needs to hear, and in what order.",
        ("Audiences", "Messages", "Sequence", "Risks"),
        "markdown",
        _rows("team", "chart", "panel"),
    ),
    _entry(
        "charter",
        "Project charter",
        "Program management",
        "Why the work exists, who sponsors it, and what done means.",
        ("Purpose", "Sponsor", "Outcomes", "Constraints"),
        "markdown",
        _CORE,
    ),
    _entry(
        "scope",
        "Scope",
        "Program management",
        "What is in the work and what is out.",
        ("In", "Out", "Dependencies"),
        "markdown",
        _rows("chart"),
    ),
    _entry(
        "workplan",
        "Workplan and Gantt",
        "Program management",
        "The sequence of work as a mermaid gantt chart.",
        ("Milestones", "Gantt", "Dependencies"),
        "mermaid",
        _rows("chart"),
    ),
    _entry(
        "raci",
        "RACI",
        "Program management",
        "Who is responsible, accountable, consulted, and informed for each step.",
        ("Steps", "RACI"),
        "table",
        _rows("chart", "team"),
    ),
    _entry(
        "risks",
        "Risks and assumptions log",
        "Program management",
        "Risks and assumptions, including a red team when one was run.",
        ("Risks", "Assumptions", "Mitigations"),
        "table",
        _rows("attacks", "panel"),
    ),
    _entry(
        "roadmap",
        "Implementation roadmap",
        "Program management",
        "What happens in 30, 60, and 90 days.",
        ("30 days", "60 days", "90 days"),
        "markdown",
        _rows("chart", "panel"),
    ),
    _entry(
        "kpi-tree",
        "KPI tree and dashboard spec",
        "Program management",
        "The measures that show the work is working, as a mermaid tree and a field list.",
        ("Outcome metric", "Drivers", "Diagram", "Fields"),
        "mermaid",
        _rows("chart", "brief"),
    ),
    _entry(
        "work-chart",
        "Work Chart",
        "Program management",
        "Today's steps and the agent-era steps, with the owner of each.",
        ("Today", "Agent era", "Summary"),
        "markdown",
        _rows("chart"),
    ),
    _entry(
        "harness-kit",
        "Harness kit",
        "Program management",
        "What the harness zip contains and how the team uses it.",
        ("Files", "Rules", "How to start"),
        "markdown",
        _rows("chart", "maturity"),
    ),
    _entry(
        "skill-pack",
        "Skill pack",
        "Program management",
        "Which skills the pack should contain for this job, within the tier cap.",
        ("Skills", "When to use each", "Cap"),
        "markdown",
        _rows("chart", "size"),
    ),
    _entry(
        "decision-note",
        "Decision validation note",
        "Political cover and decision validation",
        "The decision, who must endorse it, and what remains a human judgment.",
        ("Decision", "Who endorses it", "What a person still decides"),
        "markdown",
        _rows("panel", "maturity"),
    ),
)

BY_ID = {item["id"]: item for item in CATALOG}

_DEFAULT_PICKS = ("research-brief", "market-sizing", "issue-tree", "work-chart", "exec-memo")
_KEYWORDS = (
    (("pric", "packaging"), "pricing-analysis"),
    (("cost", "inventory", "procurement"), "cost-reduction"),
    (("due diligence", "acquisition", "target"), "due-diligence"),
    (("operating model", "org design", "reorgan"), "operating-model"),
    (("vendor", "tool"), "vendor-evaluation"),
    (("roadmap", "implement"), "roadmap"),
)


def by_id(artifact_id):
    return BY_ID.get(artifact_id)


def groups():
    ordered = []
    for name, score in TASKS:
        items = [item for item in CATALOG if item["group"] == name]
        ordered.append({"task": name, "score": score, "artifacts": items})
    return ordered


def recommend(state):
    text = " ".join(
        [
            str((state or {}).get("problem") or ""),
            str((state or {}).get("service_line") or ""),
        ]
    ).lower()
    picks = list(_DEFAULT_PICKS)
    for words, artifact_id in _KEYWORDS:
        if any(word in text for word in words) and artifact_id not in picks:
            picks.append(artifact_id)
    if len(picks) > 6:
        picks = list(_DEFAULT_PICKS[:4]) + [item for item in picks if item not in _DEFAULT_PICKS][:2]
    return picks[:6]

"""Record one mocked retail job as fixtures/retail-engagement.json."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.chatjob import handle_turn

PROMPT = (
    "Reduce inventory carrying costs across 200 stores. "
    "Team: 6 planners. Tools: Excel and SAP. Maturity 2. The client is small."
)

PANEL = {
    "service_line": "Retail operations",
    "personas": [
        {
            "name": "Amina Shah",
            "title": "Store operations lead",
            "insight": "The extra stock sits in the back room, not on the shelf.",
            "recommendation": "Count back-room units before changing the reorder point.",
        },
        {
            "name": "Luis Ortega",
            "title": "Inventory planner",
            "insight": "One reorder point for 200 stores overbuys the slow stores.",
            "recommendation": "Set the reorder point by store, not by chain.",
        },
        {
            "name": "Priya Raman",
            "title": "Finance partner",
            "insight": "Carrying cost is the holding rate times the units above the target.",
            "recommendation": "Report carrying cost by store each week.",
        },
        {
            "name": "Owen Blake",
            "title": "Supply planner",
            "insight": "A lower target fails if the supplier lead time is wrong.",
            "recommendation": "Check lead time before cutting the target.",
        },
    ],
    "consensus": "Count the stock, then set a reorder point by store.",
    "dissent": "Owen Blake wants the lead time checked before the target moves.",
    "now": ["Count back-room stock", "List stores over the target"],
    "next": ["Set reorder points by store"],
    "later": ["Review the holding rate"],
}

CHART = {
    "summary": "Agents count the stock and a planner approves the buy.",
    "current": [
        {"step": "Store count", "task": "Planners count units in each store.", "owner": "Human"},
        {"step": "Reorder sheet", "task": "A planner writes the reorder point.", "owner": "Human"},
        {"step": "Buyer approval", "task": "A buyer places the order.", "owner": "Human"},
    ],
    "future": [
        {"step": "Count the stock", "task": "An agent counts on-hand units by store.", "owner": "AI Agent"},
        {"step": "Set the reorder point", "task": "An agent drafts the reorder point from the count.", "owner": "Hybrid"},
        {"step": "Flag the exceptions", "task": "An agent lists stores over the holding target.", "owner": "AI Agent"},
        {"step": "Approve the buy", "task": "A planner approves the purchase.", "owner": "Human"},
    ],
}


def complete(name, messages, schema, max_tokens):
    if name == "ChatPanel":
        return PANEL
    if name == "ChatChart":
        return CHART
    if name == "ChatResearch":
        return {
            "facts": ["The chain has 200 stores.", "The team uses Excel and SAP."],
            "queries": [
                "retail inventory carrying cost benchmark",
                "store reorder point practice",
                "retail inventory holding cost",
            ],
        }
    if name == "ChatBrief":
        return {
            "summary": (
                "Carrying cost is the stock held above the reorder point. "
                "Across 200 stores, one chain-wide reorder point overbuys the slow stores."
            ),
            "citations": [
                {
                    "title": "Inventory holding cost note",
                    "url": "https://example.com/inventory-holding-cost",
                    "note": "Holding cost is the rate times the units held.",
                },
                {
                    "title": "Store replenishment benchmark",
                    "url": "https://example.com/store-replenishment",
                    "note": "Reorder points are set by location.",
                },
            ],
        }
    if name == "ChatSkills":
        return {
            "skills": [
                {
                    "name": "Count the stock",
                    "description": "Use this skill when the store count has not been taken.",
                    "tools": ["web_search"],
                },
                {
                    "name": "Set the reorder point",
                    "description": "Use this skill when the count is in and the reorder point is next.",
                    "tools": [],
                },
                {
                    "name": "Flag the exceptions",
                    "description": "Use this skill when a store is over the holding target.",
                    "tools": [],
                },
            ]
        }
    raise AssertionError(name)


def main():
    message = PROMPT
    state = {}
    result = None
    for _ in range(8):
        result = handle_turn(state, message, complete, recall=lambda *_: "", remember=lambda *_: None, search=_search)
        message = ""
        state = result["state"]
        if state.get("phase") == "done":
            break
    if state.get("phase") != "done":
        raise SystemExit(f"job stopped at {state.get('phase')}")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "retail-engagement.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    print(out)


def _search(query, limit=4):
    return [
        {
            "title": "Inventory holding cost note",
            "url": "https://example.com/inventory-holding-cost",
            "content": "Holding cost is the rate times the units held.",
            "date": "2026-01-01",
        },
        {
            "title": "Store replenishment benchmark",
            "url": "https://example.com/store-replenishment",
            "content": "Reorder points are set by location.",
            "date": "2025-11-01",
        },
    ]


if __name__ == "__main__":
    main()

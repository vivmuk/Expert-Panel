"""The voice guide may only return one of these actions."""

PAGES = (
    "/chat",
    "/demos",
    "/demos/maritime",
    "/demos/keiki",
    "/demos/orchid",
    "/deck",
    "/catalog",
    "/connect",
)

SECTIONS = ("hero", "demos", "catalog", "connect", "artifacts", "steps")
SNIPPETS = ("gpt", "claude", "cursor", "openai", "openaijs", "anthropic", "curl")
SLUGS = ("maritime", "keiki", "orchid")

WELCOME = "I am the AI Partner guide. Hold the button and tell me where to go, or start the tour."

TOUR = (
    "This is the start. Describe the business problem, then press Solve it.",
    "Demos shows three public engagements: Maritime, Keiki, and Orchid.",
    "The deck is the thesis, from the invoice to the resident model.",
    "The catalog lists every artifact a consulting engagement can produce.",
    "Connect has the setup you paste into ChatGPT, Claude, or Cursor.",
)


def validate_action(raw):
    if not isinstance(raw, dict):
        return None
    action = raw.get("action")
    say = _say(raw.get("say"))
    if action == "navigate" and raw.get("page") in PAGES:
        return {"action": "navigate", "page": raw["page"], "say": say or "Opening that page."}
    if action == "scroll_to" and raw.get("section") in SECTIONS:
        return {"action": "scroll_to", "section": raw["section"], "say": say or "Moving to that section."}
    if action == "fill_problem":
        text = _text(raw.get("text"), 500)
        if text:
            return {"action": "fill_problem", "text": text, "say": say or "I put that in the problem box."}
    if action == "set_depth" and raw.get("depth") in ("strategy", "full"):
        return {"action": "set_depth", "depth": raw["depth"], "say": say or "Depth updated."}
    if action == "start_engagement":
        return {"action": "start_engagement", "say": say or "Starting the engagement."}
    if action == "open_demo" and raw.get("slug") in SLUGS:
        return {"action": "open_demo", "slug": raw["slug"], "say": say or "Opening that demo."}
    if action == "copy_snippet" and raw.get("id") in SNIPPETS:
        return {"action": "copy_snippet", "id": raw["id"], "say": say or "Copied."}
    if action == "answer":
        text = _text(raw.get("text"), 400) or say
        if text:
            return {"action": "answer", "text": text, "say": text}
    return None


def _say(value):
    return _text(value, 240)


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]

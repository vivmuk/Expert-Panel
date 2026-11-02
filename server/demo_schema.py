"""Shape of a stored demo engagement. Citations are kept only when their URL was returned by search."""

DISCLAIMER = "AI-generated demo engagement from public information. Not commissioned by the company."
LEGACY_DISCLAIMERS = ("Demo engagement generated from public information. Not commissioned by the company.",)
LEVELS = ("high", "medium", "low")

SLUGS = {
    "maritime": "Maritime",
    "keiki": "Keiki",
    "orchid": "Orchid",
}


def empty_demo(slug, problem):
    return {
        "slug": slug,
        "company": SLUGS[slug],
        "disclaimer": DISCLAIMER,
        "generated": False,
        "problem": problem.strip(),
        "market": {"summary": "", "citations": []},
        "experts": [],
        "debate": [],
        "top5": [],
        "maturity": None,
        "chart": None,
        "skills": [],
        "artifacts": [],
        "kit": f"/demos/{slug}/kit.zip",
    }


def keep_citations(items, allowed):
    found = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url or url not in allowed or url in seen:
            continue
        seen.add(url)
        found.append(
            {
                "title": str(item.get("title") or url)[:180],
                "url": url,
                "note": str(item.get("note") or item.get("content") or "")[:240],
            }
        )
    return found


def level(value):
    text = str(value or "").strip().lower()
    return text if text in LEVELS else ""


def skill_entry(item):
    """A skill is {name, purpose, files}. Older files stored a bare name."""
    if isinstance(item, str):
        return {"name": item, "purpose": "", "files": []}
    if not isinstance(item, dict) or not item.get("name"):
        return None
    files = [str(path) for path in (item.get("files") or []) if isinstance(path, str)]
    return {"name": str(item["name"]), "purpose": str(item.get("purpose") or ""), "files": files}


def valid_demo(data):
    if not isinstance(data, dict):
        return False
    if data.get("slug") not in SLUGS:
        return False
    if data.get("disclaimer") not in (DISCLAIMER,) + LEGACY_DISCLAIMERS:
        return False
    if not isinstance(data.get("problem"), str) or not data["problem"].strip():
        return False
    market = data.get("market")
    if not isinstance(market, dict) or not isinstance(market.get("citations"), list):
        return False
    for key in ("experts", "debate", "top5", "skills", "artifacts"):
        if not isinstance(data.get(key), list):
            return False
    return True

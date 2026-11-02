import io
import zipfile

from server.artifacts import generate_artifact
from server.catalog import CATALOG, FORMATS, INPUTS, TASKS, by_id, groups, recommend
from server.harnesskit import build_kit_zip
from tests.test_chatjob import CHART, PANEL


def _state():
    return {
        "chat_id": "catalog-job",
        "phase": "ask_size",
        "problem": "Reduce inventory carrying costs across 200 stores.",
        "team": "6 planners",
        "tools": "Excel",
        "maturity": 2,
        "service_line": "Retail operations",
        "size": "small",
        "panel": PANEL,
        "chart": CHART,
        "brief": {
            "summary": "Carrying cost is the stock above the reorder point.",
            "citations": [{"title": "Holding cost", "url": "https://example.com/holding", "note": "rate times units"}],
        },
        "calls": 1,
    }


def test_every_catalog_entry_is_well_formed():
    ids = [item["id"] for item in CATALOG]
    assert len(ids) == len(set(ids))
    assert len(CATALOG) >= 24
    task_names = {name for name, _score in TASKS}
    for item in CATALOG:
        assert item["group"] in task_names
        assert item["title"]
        assert item["purpose"]
        assert item["sections"]
        assert item["format"] in FORMATS
        assert item["inputs"]
        assert set(item["inputs"]) <= set(INPUTS)
    assert {group["task"] for group in groups()} == task_names


def test_generator_returns_the_entry_sections():
    entry = by_id("charter")

    def complete(name, messages, schema, max_tokens):
        assert name == "ChatArtifact"
        assert "assumption" in messages[0]["content"].lower()
        assert "Do not invent" in messages[0]["content"]
        body = "\n\n".join(f"## {section}\n\nText." for section in entry["sections"])
        assert all(section in messages[1]["content"] for section in entry["sections"])
        return {"markdown": body}

    result = generate_artifact(_state(), "charter", complete)
    for section in entry["sections"]:
        assert f"## {section}" in result["markdown"]
    assert result["state"]["artifacts"]["charter"] == result["markdown"]


def test_strategy_tier_stops_at_five_artifacts():
    state = _state()
    state["artifacts"] = {f"extra-{index}": "x" for index in range(5)}
    # only real ids count; fill with five real ones
    ids = [item["id"] for item in CATALOG if item["id"] != "charter"][:5]
    state["artifacts"] = {artifact_id: "## Done\n" for artifact_id in ids}

    def complete(name, messages, schema, max_tokens):
        raise AssertionError("should not call the model")

    try:
        generate_artifact(state, "charter", complete)
    except Exception as exc:
        assert getattr(exc, "code", "") == "limit"
    else:
        raise AssertionError("expected the strategy cap")


def test_full_depth_can_pass_the_strategy_cap():
    state = _state()
    state["depth"] = "full"
    ids = [item["id"] for item in CATALOG if item["id"] != "workshop"][:5]
    state["artifacts"] = {artifact_id: "## Done\n" for artifact_id in ids}

    def complete(name, messages, schema, max_tokens):
        return {"markdown": "## Purpose\n\nA session.\n\n## Agenda\n\nOne hour.\n\n## Materials\n\nNone.\n\n## Decisions to leave with\n\nNone."}

    result = generate_artifact(state, "workshop", complete)
    assert "workshop" in result["state"]["artifacts"]


def test_kit_zip_includes_generated_artifacts():
    state = _state()
    state["artifacts"] = {"charter": "## Purpose\n\nRun the count.\n"}
    blob = build_kit_zip(state)
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "artifacts/charter.md" in names


def test_recommendations_stay_between_five_and_six():
    assert len(recommend({"problem": "A general question"})) == 5
    picks = recommend({"problem": "Reduce inventory carrying costs"})
    assert 5 <= len(picks) <= 6
    assert "cost-reduction" in picks


def test_catalog_and_pricing_pages_and_mcp_tools(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("AI_PARTNER_API_KEYS", "partner-test-key")
    from server import create_app

    client = create_app().test_client()
    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert b"Data gathering and market research" in catalog.data
    assert b"Market sizing" in catalog.data
    pricing = client.get("/pricing")
    assert b"$10" in pricing.data
    assert b"up to 5 catalog artifacts" in pricing.data
    assert b"Harness Build" in pricing.data
    assert b"/catalog" in pricing.data
    listed = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Authorization": "Bearer partner-test-key"},
    )
    names = [tool["name"] for tool in listed.get_json()["result"]["tools"]]
    assert "list_artifacts" in names
    assert "generate_artifact" in names

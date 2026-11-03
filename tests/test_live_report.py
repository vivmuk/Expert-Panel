import io
import json
import os
import re

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "live_engagement.json")
SECTIONS = ("summary", "market", "experts", "debate", "synthesis", "top5", "maturity", "chart", "skills", "artifacts")


@pytest.fixture
def state():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def client():
    from server import create_app

    return create_app().test_client()


def test_live_engagement_maps_onto_the_demo_report(state):
    from server.live_report import live_demo

    demo = live_demo(state)
    assert demo["live"] is True
    assert len(demo["experts"]) == 20
    assert all(e["recommendation"] and e["insight"] for e in demo["experts"])
    assert sum(len(e["said"]) for e in demo["experts"]) == 40
    assert len(demo["market"]["citations"]) == len(state["sources"])
    assert all(c["note"] for c in demo["market"]["citations"])
    assert len(demo["synthesis"]["judges"]) == 4
    assert [s["priority"] for s in demo["synthesis"]["actionable_next_steps"]][:1] == ["Now"]
    assert demo["maturity"]["score"] == state["maturity"]
    assert len(demo["artifacts"]) == 5


def test_view_returns_the_full_report_and_five_deliverables(client, state):
    res = client.post("/api/chat/view", json={"state": state})
    assert res.status_code == 200
    data = res.get_json()
    report = data["report"]
    for key in SECTIONS:
        assert f'id="{key}"' in report
    assert report.count('class="expert-card"') == 20
    assert report.count("<li data-round=") == 40
    assert 'data-expand="expert-list"' in report
    assert report.count('class="swim-row"') == len(state["chart"]["future"])
    assert report.count('data-card="') == 5
    assert 'data-download="pptx"' in report
    assert "Not commissioned" not in report
    ids = [d["id"] for d in data["deliverables"]]
    assert ids == ["deck", "exec-memo", "work-chart", "research-brief", "roadmap"]
    for doc in data["deliverables"]:
        assert doc["html"].startswith("<!DOCTYPE html>")
        assert "#0033CC" in doc["html"] and "#D7263D" in doc["html"]
        assert doc["markdown"].startswith("# ")
    docs = {d["id"]: d["html"] for d in data["deliverables"]}
    assert "Memorandum" in docs["exec-memo"] and "Bottom line" in docs["exec-memo"]
    assert 'class="own hybrid"' in docs["work-chart"] and 'class="swim"' in docs["work-chart"]
    assert docs["research-brief"].count('class="src"') == len(state["sources"])
    assert 'class="matrix"' in docs["roadmap"]
    assert docs["deck"].count('<section class="slide') >= 14


def test_view_refuses_an_unfinished_engagement(client, state):
    state = dict(state, chart=None)
    assert client.post("/api/chat/view", json={"state": state}).status_code == 400
    assert client.post("/api/chat/deck.pptx", json={"state": state}).status_code == 400


def test_deck_downloads_as_a_real_pptx(client, state):
    from pptx import Presentation

    res = client.post("/api/chat/deck.pptx", json={"state": state})
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.presentationml")
    deck = Presentation(io.BytesIO(res.data))
    assert len(deck.slides) >= 14
    text = " ".join(shape.text_frame.text for slide in deck.slides for shape in slide.shapes if shape.has_text_frame)
    assert state["top5"][0]["title"] in text
    assert any(shape.shape_type == 13 for shape in deck.slides[0].shapes)


def test_catalog_artifact_markdown_becomes_a_styled_page():
    from server.artifact_doc import as_html

    html = as_html("Issue tree", "# Issue tree\n\n## Root\n\n- **Cost** is up\n- Time\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```mermaid\nflowchart TD\n```")
    assert "<h2>Root</h2>" in html
    assert "<ul><li><b>Cost</b> is up</li><li>Time</li></ul>" in html
    assert "<td>1</td>" in html
    assert '<pre class="code">flowchart TD</pre>' in html
    assert "<h1>Issue tree</h1>" in html and html.count("Issue tree</h1>") == 1


def test_chat_page_loads_the_report_renderer(client):
    page = client.get("/chat").get_data(as_text=True)
    assert '<link rel="stylesheet" href="/report.css">' in page
    assert re.search(r'<script src="/report.js" defer></script>\s*<script src="/chat.js"', page)


def test_demo_report_uses_the_same_swimlanes_and_expand_all(client):
    page = client.get("/demos/maritime").get_data(as_text=True)
    assert 'data-expand="expert-list"' in page
    assert 'class="swim"' in page
    assert 'class="deliverable-grid"' in page


def test_numbered_chart_steps_get_named_skills(state):
    from server.skillpack import pack_manifest

    names = [s["name"] for s in pack_manifest(state)["skills"]]
    assert names and not any(name.isdigit() for name in names)

from server.demo_pipeline import run_demo
from server.demo_schema import valid_demo
from server.voice_actions import validate_action


def test_voice_whitelist_accepts_a_page_and_rejects_code():
    assert validate_action({"action": "navigate", "page": "/demos", "say": "Opening demos."})["page"] == "/demos"
    assert validate_action({"action": "open_demo", "slug": "orchid", "say": "Opening Orchid."})["slug"] == "orchid"
    assert validate_action({"action": "navigate", "page": "javascript:alert(1)", "say": "No."}) is None
    assert validate_action({"action": "eval", "say": "No."}) is None


def test_stored_demos_match_the_schema():
    import json
    from pathlib import Path

    folder = Path("server/static/demos")
    for slug in ("maritime", "keiki", "orchid"):
        data = json.loads((folder / f"{slug}.json").read_text())
        assert valid_demo(data)
        assert data["slug"] == slug
        assert "Not commissioned" in data["disclaimer"]
        assert data["market"]["citations"]
        assert all(item["url"].startswith("http") for item in data["market"]["citations"])


def test_pipeline_drops_citations_that_search_did_not_return():
    allowed = "https://maritime.sh/docs/web-apps"

    def search(query, limit=4):
        return [{"title": "Public web agents", "url": allowed, "content": "Docs.", "date": ""}]

    def complete(name, messages, schema, max_tokens):
        if name == "ChatDemoQueries":
            return {"queries": ["Maritime public web agents"]}
        if name == "ChatDemoMarket":
            return {
                "summary": "The docs describe public web agents.",
                "citations": [
                    {"title": "Docs", "url": allowed, "note": "Docs."},
                    {"title": "Invented", "url": "https://evil.example/nope", "note": "no"},
                ],
            }
        if name == "ChatDemoExperts":
            return {"experts": [{"name": "Ada", "role": "Operator", "background": "Runs agents.", "lens": "Hosting"}]}
        if name == "ChatDemoFeedback":
            return {"risks": "Cold start.", "opportunities": "A public URL.", "recommendation": "Ship a health check."}
        if name == "ChatDemoDebate":
            return {"statement": "Start with the health check.", "responding_to": "Ada"}
        if name == "ChatDemoJudge":
            return {"recommendations": [{
                "title": "Ship the health check",
                "detail": "The docs show a public web agent.",
                "citation_url": "https://evil.example/nope",
                "backers": ["Ada"],
                "dissenters": [],
                "confidence": "Medium",
                "impact": "high",
                "effort": "huge",
            }]}
        if name == "ChatDemoMaturity":
            return {"score": 2, "reason": "A pilot."}
        if name == "ChatDemoChart":
            return {
                "summary": "Agents host the app.",
                "current": [
                    {"step": "Deploy", "task": "A person deploys.", "owner": "Human"},
                    {"step": "Watch", "task": "A person watches logs.", "owner": "Human"},
                    {"step": "Decide", "task": "A person decides.", "owner": "Human"},
                ],
                "future": [
                    {"step": "Deploy", "task": "An agent deploys.", "owner": "AI Agent"},
                    {"step": "Watch", "task": "An agent watches logs.", "owner": "Hybrid"},
                    {"step": "Decide", "task": "A person decides.", "owner": "Human"},
                ],
            }
        if name in ("ChatDemoSynthesis", "ChatDemoSkills", "ChatDemoHarness"):
            return {}
        raise AssertionError(name)

    demo = run_demo("maritime", "Host a public web agent.", complete, search)
    urls = [item["url"] for item in demo["market"]["citations"]]
    assert urls == [allowed]
    assert demo["top5"][0]["citation_url"] == ""
    assert demo["experts"][0]["badge"] == "AI-generated expert"
    assert len(demo["debate"]) == 2
    top = demo["top5"][0]
    assert (top["confidence"], top["impact"], top["effort"]) == ("medium", "high", "")
    names = [skill["name"] for skill in demo["skills"]]
    assert names == ["run-the-engagement", "deploy", "watch"]
    assert all(skill["purpose"] and skill["files"][0].endswith("/SKILL.md") for skill in demo["skills"])
    assert not any(name.startswith("skill-") for name in names)
    assert demo["disclaimer"].startswith("AI-generated demo engagement")
    assert valid_demo(demo)


def test_artifact_html_carries_the_demo_footer():
    from server.artifact_doc import as_html, as_markdown

    html = as_html("Charter", "## Purpose\n\nRun the count.", demo=True)
    assert "Playfair Display" in html
    assert "AI-generated demo engagement from public information. Not commissioned by the company." in html
    assert "<h2>Purpose</h2>" in html
    assert "AI-generated demo engagement from public information. Not commissioned by the company." in as_markdown("Charter", "Body", demo=True)


def test_demo_page_renders_the_disclaimer(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    from server import create_app

    client = create_app().test_client()
    page = client.get("/demos/maritime")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "Not commissioned by the company." in text
    assert "Executive summary" in text
    assert 'id="market"' in text
    assert "https://maritime.sh/docs/web-apps" in text
    assert "Cal.com" not in text
    summary, market = text.split('id="market"', 1)
    market = market.split('id="experts"', 1)[0]
    debate, top5 = text.split('id="debate"', 1)[1].split('id="top5"', 1)
    top5 = top5.split('id="maturity"', 1)[0]
    skills = text.split('id="skills"', 1)[1].split('id="artifacts"', 1)[0]
    assert summary.index("maritime-cover.webp") < summary.index("<h1>")
    assert market.index("Market analysis") < market.index("maritime-market.webp")
    assert debate.index("Debate") < debate.index("maritime-panel.webp")
    assert "Top 5" in top5 and 'id="recs"' in top5
    assert skills.index("Harness and skill pack") < skills.index("maritime-build.webp")
    assert 'href="/demos/maritime/deck"' in summary and "Open the client deck" in summary
    for slug in ("keiki", "orchid"):
        other = client.get(f"/demos/{slug}").get_data(as_text=True)
        for kind in ("cover", "market", "panel", "build"):
            assert f"{slug}-{kind}.webp" in other
    index = client.get("/demos")
    assert b"Keiki" in index.data and b"Orchid" in index.data
    chat = client.get("/chat")
    assert b"/voice.js" in chat.data
    assert b'id="guide-talk"' in client.get("/voice.js").data


def test_text_plan_uses_only_the_whitelist(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")

    class Fake:
        def structured(self, *args, **kwargs):
            return {"action": "open_demo", "slug": "keiki", "say": "Opening Keiki."}

    monkeypatch.setattr("server.api.voice.VeniceClient", Fake)
    monkeypatch.setattr("server.api.voice._speak", lambda text: b"")
    from server import create_app

    client = create_app().test_client()
    res = client.post("/api/voice/plan", json={"text": "show keiki"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["heard"] == "show keiki"
    assert body["action"]["action"] == "open_demo"
    assert body["action"]["slug"] == "keiki"
    assert body["captions"] == "Opening Keiki."


def _client(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("VERCEL", "1")
    from server import create_app

    return create_app().test_client()


def test_client_decks_and_every_kit_link_they_use_serve(monkeypatch):
    import re
    from pathlib import Path

    client = _client(monkeypatch)
    for slug in ("maritime", "keiki", "orchid"):
        deck = client.get(f"/demos/{slug}/deck")
        assert deck.status_code == 200
        assert deck.mimetype == "text/html"
        html = deck.get_data(as_text=True)
        assert html == Path(f"server/static/demos/{slug}/deck.html").read_text(encoding="utf-8")
        assert client.get(f"/demos/{slug}/deck/").status_code == 200
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', html)
        assert srcs and all(s.startswith("data:image/webp;base64,") for s in srcs)
        links = set(re.findall(r'href="https://[^/"]+(/demos/[^"]+)"', html))
        assert f"/demos/{slug}/kit.zip" in links
        assert len(links) >= 7
        for path in links:
            res = client.get(path)
            assert res.status_code == 200, path
            if path.endswith(".json"):
                assert res.mimetype == "application/json"
        assert client.get(f"/demos/{slug}/kit.zip").mimetype == "application/zip"
    assert client.get("/demos/nope/deck").status_code == 404
    assert client.get("/demos/maritime/kit/../../maritime.json").status_code == 404


def test_inner_page_art_has_alt_text_sizes_and_lazy_loading(monkeypatch):
    import re

    client = _client(monkeypatch)
    for path in ("/what-you-get", "/catalog", "/demos", "/demos/maritime", "/demos/keiki", "/demos/orchid"):
        html = client.get(path).get_data(as_text=True)
        art = [tag for tag in re.findall(r"<img [^>]+>", html) if re.search(r'src="/(img/(catalog|what-you-get|brand/hero)|demos/img)/', tag)]
        assert art, path
        for tag in art:
            assert re.search(r'alt="[^"]{20,}"', tag), tag
            assert 'width="' in tag and 'height="' in tag, tag
            assert 'loading="lazy"' in tag or 'fetchpriority="high"' in tag, tag
    home = client.get("/chat").get_data(as_text=True)
    assert "hero.webp" not in home
    assert not re.search(r'src="/(img/(catalog|what-you-get)|demos/img)/', home)


def _iframe(html, src):
    import re

    tags = [tag for tag in re.findall(r"<iframe [^>]+>", html) if f'src="{src}"' in tag]
    assert len(tags) == 1, src
    return tags[0]


def test_decks_are_embedded_inline_with_same_origin_framing(monkeypatch):
    import re
    from pathlib import Path

    client = _client(monkeypatch)
    for slug in ("maritime", "keiki", "orchid"):
        html = client.get(f"/demos/{slug}").get_data(as_text=True)
        tag = _iframe(html, f"/demos/{slug}/deck")
        assert re.search(r'title="[^"]{10,}"', tag) and 'loading="lazy"' in tag and "allowfullscreen" in tag
        assert "tabindex=\"-1\"" not in tag
        assert html.index('class="exec card"') < html.index("data-deck-embed") < html.index('id="market"')
        assert "data-deck-fullscreen" in html and "Open in new tab" in html and "/deck-embed.js" in html
        assert "14 slides" in html
        deck = client.get(f"/demos/{slug}/deck")
        assert deck.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert deck.headers["Content-Security-Policy"] == "frame-ancestors 'self'"

    about = client.get("/about")
    assert about.status_code == 200
    html = about.get_data(as_text=True)
    assert "The First 1,000" in html and "/deck-embed.js" in html
    _iframe(html, "/deck")
    deck = client.get("/deck")
    assert deck.data == Path("server/static/deck/index.html").read_bytes()
    assert deck.headers["X-Frame-Options"] == "SAMEORIGIN"

    home = client.get("/chat").get_data(as_text=True)
    assert "<iframe" not in home and "deck-embed" not in home
    assert client.get("/deck-embed.js").status_code == 200

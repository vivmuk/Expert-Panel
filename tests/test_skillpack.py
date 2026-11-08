import base64
import io
import json
import zipfile

from server.chatjob import handle_turn
from server.exa_search import EXA_URL, exa_search
from server.skillpack import MAX_SKILLS, STRATEGY_SKILLS, pack_files
from server.uploads import take_uploads
from tests.test_chatjob import ONE_SHOT, fake_model, run_until_stop


def _chart(count):
    return {
        "summary": "Agents draft and a partner decides.",
        "current": [
            {"step": "Desk research", "task": "People pull sources.", "owner": "Human"},
            {"step": "Partner review", "task": "A partner decides.", "owner": "Human"},
        ],
        "future": [
            {"step": f"Step {index}", "task": f"Do step {index}.", "owner": "AI Agent"}
            for index in range(count)
        ],
    }


def _state(tier, count):
    return {
        "size": tier,
        "problem": "Pricing for a B2B analytics product",
        "service_line": "Pricing",
        "team": "3 managers",
        "tools": "Excel",
        "maturity": 2,
        "chart": _chart(count),
        "brief": {
            "summary": "Price from the usage data.",
            "citations": [{"title": "Bench", "url": "https://example.com/bench", "note": "annual"}],
        },
        "facts": ["The team uses Excel."],
        "uploads": [],
        "skill_notes": {},
    }


def _manifest(files):
    return json.loads(files["skills/skills.json"])


def test_small_tier_is_task_skills_capped_at_3():
    files = pack_files(_state("small", 12))
    manifest = _manifest(files)
    assert manifest["tier"] == "small"
    assert len(manifest["skills"]) == STRATEGY_SKILLS
    assert [item["level"] for item in manifest["skills"]] == ["task"] * STRATEGY_SKILLS
    _assert_frontmatter(files, manifest)


def test_medium_tier_uses_the_same_three_skill_cap():
    files = pack_files(_state("medium", 12))
    manifest = _manifest(files)
    assert len(manifest["skills"]) == STRATEGY_SKILLS
    assert [item["level"] for item in manifest["skills"]] == ["task"] * STRATEGY_SKILLS
    _assert_frontmatter(files, manifest)


def test_large_tier_stops_at_10_including_the_orchestrator():
    files = pack_files(_state("large", 12))
    manifest = _manifest(files)
    assert len(manifest["skills"]) == MAX_SKILLS
    assert manifest["skills"][0]["level"] == "orchestrator"
    assert len(manifest["skills"][0]["dependencies"]["skills"]) == 9
    _assert_frontmatter(files, manifest)


def test_client_template_is_listed_with_the_work_it_supports():
    state = _state("small", 2)
    state["uploads"] = [
        {
            "name": "memo-template.md",
            "kind": "template",
            "text": "Draft for Step 0. Hello {{name}}.",
        }
    ]
    files = pack_files(state)
    readme = files["skills/step-0/templates/README.md"]
    assert "memo-template.md supports Step 0" in readme
    client_files = [text for path, text in files.items() if "client-memo" in path]
    assert client_files
    assert "Hello {{name}}" in client_files[0]


def test_default_artifacts_use_the_vivdesign_palette():
    files = pack_files(_state("small", 1))
    html = files["skills/step-0/templates/one-pager.html"]
    assert "#7fb2ff" in html
    assert "#c084fc" in html
    assert "Playfair Display" in html
    assert "DM Sans" in html
    assert "https://designviv.up.railway.app" in html


def _assert_frontmatter(files, manifest):
    assert manifest["style"] == "vivDesign"
    for skill in manifest["skills"]:
        assert set(skill["dependencies"]) == {"tools", "mcps", "packages", "skills"}
        body = files[f"{skill['path']}/SKILL.md"]
        head, _, _rest = body.partition("\n---\n")
        assert head.startswith("---\n")
        assert f"name: {skill['name']}" in head
        assert "description: " in head
        assert "Use this skill when" in head
        assert f"{skill['path']}/scripts/render.py" in files
        assert "https://example.com/bench" in files[f"{skill['path']}/references/research.md"]


def test_exa_request_matches_the_documented_shape(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    seen = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "G-BA",
                        "url": "https://example.com/gba",
                        "content": "Codes update yearly.",
                        "date": "2026-01-02",
                    }
                ]
            }

    def post(url, headers, json, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("server.exa_search.requests.post", post)
    from server.spendguard import provider_window

    with provider_window():
        found = exa_search("german reimbursement", limit=25)
    assert seen["url"] == EXA_URL
    assert seen["url"] == "https://api.venice.ai/api/v1/augment/search"
    assert seen["headers"]["Authorization"] == "Bearer test-not-a-real-key"
    assert seen["json"] == {
        "query": "german reimbursement",
        "limit": 20,
        "search_provider": "exa",
    }
    assert found[0]["url"] == "https://example.com/gba"
    assert found[0]["date"] == "2026-01-02"


def test_research_keeps_exa_urls_through_the_skill_pack():
    calls = []

    def search(query, limit=4):
        assert 1 <= limit <= 20
        return [
            {
                "title": "G-BA",
                "url": "https://example.com/gba",
                "content": "Codes update yearly.",
                "date": "2026-01-02",
            }
        ]

    complete = fake_model(calls)
    researched = handle_turn({}, ONE_SHOT + " The client is small.", complete, search=search)
    assert "https://example.com/gba" in researched["reply"]
    briefed = handle_turn(researched["state"], "", complete, search=search)
    assert "https://example.com/gba" in briefed["reply"]
    finished = run_until_stop(briefed, complete, search=search)
    assert finished["state"]["phase"] == "done"
    assert finished["state"]["size"] == "small"
    blob = __import__("server.skillpack", fromlist=["build_pack_zip"]).build_pack_zip(finished["state"])
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = set(archive.namelist())
    assert "skills/skills.json" in names
    assert "skills/README.md" in names
    skill = [name for name in names if name.endswith("SKILL.md") and "source-sweep" in name]
    assert skill
    text = archive.read(skill[0]).decode()
    assert text.startswith("---\n")
    assert "Use this skill when" in text.split("---", 2)[1]
    assert "https://example.com/gba" in archive.read("skills/source-sweep/references/research.md").decode()


def test_docx_upload_becomes_text():
    document = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Template for Step 0.</w:t></w:r></w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", document)
    encoded = base64.b64encode(buf.getvalue()).decode()
    parsed = take_uploads([{"name": "memo-template.docx", "base64": encoded}], [])
    assert parsed[0]["text"] == "Template for Step 0."
    assert parsed[0]["kind"] == "template"

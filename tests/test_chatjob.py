import io
import zipfile

import pytest

from server.api.chat import TURN_LIMIT, reset_limits
from server.chatjob import MAX_OUTPUT_TOKENS, handle_turn, render_report
from server.chatmemory import recall, remember
from server.config import Config
from server.harnesskit import build_kit_zip

ONE_SHOT = (
    "Market entry for a medtech device into Germany. "
    "Team: 4 analysts. Tools: Excel and Veeva. Maturity 2."
)

PANEL = {
    "service_line": "Market entry",
    "personas": [
        {"name": "Ada", "title": "Market access lead", "insight": "Reimbursement decides the first year.", "recommendation": "File the dossier with a local partner."},
        {"name": "Bao", "title": "Hospital buyer", "insight": "Committees buy from vendors they already know.", "recommendation": "Borrow a reference site before the launch."},
        {"name": "Chen", "title": "Regulatory counsel", "insight": "The label claim is the constraint.", "recommendation": "Freeze the claim before the commercial plan."},
        {"name": "Dia", "title": "Medical affairs", "insight": "KOLs will not brief from a US slide.", "recommendation": "Commission a local evidence brief."},
    ],
    "consensus": "Enter Germany with a local partner.",
    "dissent": "One persona wants to wait for the code.",
    "now": ["Map the payers", "Pick the partner"],
    "next": ["File the dossier"],
    "later": ["Hire the local team"],
}

ATTACKS = {
    "top_risk": "Reimbursement codes lag the launch.",
    "attacks": [
        {"threat": "Code delay", "why": "The local catalogue moves yearly.", "mitigation": "File the code request before hiring."},
        {"threat": "Tender lockout", "why": "Incumbents hold the framework.", "mitigation": "Bid as a subcontractor first."},
        {"threat": "Claim mismatch", "why": "The US label does not transfer.", "mitigation": "Rewrite the claim with local counsel."},
    ],
}

CHART = {
    "summary": "Agents draft the memo and a partner decides.",
    "current": [
        {"step": "Desk research", "task": "Analysts pull German sources.", "owner": "Human"},
        {"step": "Draft memo", "task": "An analyst writes the memo.", "owner": "Human"},
        {"step": "Partner review", "task": "A partner edits the memo.", "owner": "Human"},
    ],
    "future": [
        {"step": "Source sweep", "task": "An agent pulls German sources.", "owner": "AI Agent"},
        {"step": "Draft memo", "task": "An agent drafts the memo.", "owner": "Hybrid"},
        {"step": "Partner decision", "task": "A partner accepts or rejects the memo.", "owner": "Human"},
    ],
}


def fake_model(calls):
    def complete(name, messages, schema, max_tokens):
        assert max_tokens <= MAX_OUTPUT_TOKENS
        calls.append(name)
        if name == "ChatPanel":
            return PANEL
        if name == "ChatRedTeam":
            return ATTACKS
        if name == "ChatChart":
            assert "Enter Germany with a local partner." in messages[-1]["content"]
            return CHART
        raise AssertionError(name)

    return complete


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_limits()
    yield
    reset_limits()


def test_three_questions_then_panel():
    calls = []
    complete = fake_model(calls)
    first = handle_turn({}, "Pricing for a B2B analytics product", complete)
    assert first["state"]["phase"] == "ask_context"
    assert "team" in first["reply"].lower()
    assert calls == []

    second = handle_turn(first["state"], "Team of 3 managers using Excel", complete)
    assert second["state"]["phase"] == "ask_maturity"
    assert "Invoice-led" in second["reply"]
    assert calls == []

    third = handle_turn(second["state"], "soon", complete)
    assert third["state"]["phase"] == "ask_maturity"
    assert calls == []

    fourth = handle_turn(third["state"], "2", complete)
    assert calls == ["ChatPanel"]
    assert "Pricing for a B2B analytics product" in fourth["state"]["problem"]
    assert fourth["state"]["tools"] == "Excel"
    assert fourth["next"] == "blueprint"
    assert fourth["state"]["maturity"] == 2
    assert "Enter Germany with a local partner." in fourth["reply"]
    assert "Ada" in fourth["reply"]


def test_one_message_can_carry_the_whole_intake():
    calls = []
    result = handle_turn({}, ONE_SHOT, fake_model(calls))
    assert calls == ["ChatPanel"]
    assert result["state"]["team"] == "4 analysts"
    assert result["state"]["tools"] == "Excel and Veeva"
    assert result["state"]["maturity"] == 2
    assert result["next"] == "blueprint"
    assert result["state"]["phase"] == "blueprint"


def test_red_team_runs_only_when_asked_then_chart_finishes():
    calls = []
    complete = fake_model(calls)
    started = handle_turn({}, ONE_SHOT + " Run a red team.", complete)
    assert started["next"] == "red_team"
    attacked = handle_turn(started["state"], "", complete)
    assert attacked["next"] == "blueprint"
    assert "Reimbursement codes lag the launch." in attacked["reply"]
    finished = handle_turn(attacked["state"], "", complete)
    assert finished["next"] is None
    assert finished["state"]["phase"] == "done"
    assert calls == ["ChatPanel", "ChatRedTeam", "ChatChart"]
    assert "Source sweep" in finished["reply"]
    assert "Owner AI Agent" in finished["reply"]
    assert "CLAUDE.md" in finished["reply"]
    assert finished["state"]["calls"] == 3


def test_budget_stops_the_model():
    calls = []
    state = {
        "chat_id": "budget1",
        "phase": "panel",
        "problem": "Pricing for a B2B analytics product",
        "team": "3 managers",
        "tools": "Excel",
        "maturity": 2,
        "calls": 4,
    }
    result = handle_turn(state, "", fake_model(calls))
    assert calls == []
    assert result["error"]["code"] == "budget"
    assert result["state"]["phase"] == "panel"
    assert "4 model calls" in result["reply"]


def test_prior_context_is_in_the_panel_brief():
    seen = {}

    def complete(name, messages, schema, max_tokens):
        seen["user"] = messages[-1]["content"]
        return PANEL

    result = handle_turn({}, ONE_SHOT, complete, recall=lambda chat_id, query: "known payer mix")
    assert "known payer mix" in seen["user"]
    assert "4 analysts" in seen["user"]
    assert "Excel" in seen["user"]
    assert result["state"]["memories"] == "known payer mix"


def test_kit_zip_contains_the_agent_skills():
    calls = []
    finished = handle_turn({}, ONE_SHOT, fake_model(calls))
    finished = handle_turn(finished["state"], "", fake_model(calls))
    blob = build_kit_zip(finished["state"])
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = set(archive.namelist())
    for required in ("CLAUDE.md", "playbook.md", "model-routing.md", "project-state-schema.md"):
        assert required in names
    skills = [name for name in names if name.endswith("SKILL.md")]
    assert "skills/source-sweep/SKILL.md" in skills
    assert "skills/draft-memo/SKILL.md" in skills
    assert "skills/partner-decision/SKILL.md" not in names
    skill = archive.read("skills/source-sweep/SKILL.md").decode()
    assert "Source sweep" in skill
    assert "AI Agent" in skill
    claude = archive.read("CLAUDE.md").decode()
    assert "Pilot-led" in claude
    assert "Germany" in claude
    routing = archive.read("model-routing.md").decode()
    assert "qwen3-next-80b" in routing
    report = render_report(finished["state"])
    assert "Pilot-led" in report
    assert "Ada" in report
    assert "Source sweep" in report


def test_kit_without_a_chart_fails():
    with pytest.raises(ValueError):
        build_kit_zip({"maturity": 2, "problem": "Pricing", "team": "", "tools": ""})


def test_recall_and_remember_are_off_without_a_key(monkeypatch):
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)

    def post(*args, **kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("server.chatmemory.requests.post", post)
    assert recall("abc", "Germany") == ""
    remember("abc", "hello")


def test_recall_posts_to_the_chat_namespace(monkeypatch):
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "test-memory-key")
    seen = {}

    class Dummy:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"memory": "known payer mix"}]}

    def post(url, headers, json, timeout):
        seen["url"] = url
        seen["auth"] = headers["Authorization"]
        seen["json"] = json
        seen["timeout"] = timeout
        return Dummy()

    monkeypatch.setattr("server.chatmemory.requests.post", post)
    assert recall("abc_123", "Germany") == "known payer mix"
    assert seen["url"] == "https://api.supermemory.ai/ns/chat-abc_123/search"
    assert seen["auth"] == "Bearer test-memory-key"
    assert seen["json"]["query"] == "Germany"
    assert seen["timeout"] <= 5


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    calls = []
    monkeypatch.setattr("server.api.chat.complete_with_venice", fake_model(calls))
    from server import create_app

    app = create_app()
    app.test_client_calls = calls
    return app.test_client()


def test_http_job_report_and_kit(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://demo.example")
    first = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}})
    assert first.status_code == 200
    body = first.get_json()
    assert body["next"] == "blueprint"
    assert body["state"]["calls"] == 1

    second = client.post("/api/chat", json={"message": "", "state": body["state"]})
    assert second.status_code == 200
    done = second.get_json()
    assert done["state"]["phase"] == "done"
    assert done["next"] is None
    assert "https://demo.example/api/chat/kit" in done["reply"]
    assert client.application.test_client_calls == ["ChatPanel", "ChatChart"]

    kit = client.post("/api/chat/kit", json={"state": done["state"]})
    assert kit.status_code == 200
    assert kit.mimetype == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(kit.data))
    assert "CLAUDE.md" in archive.namelist()
    assert any(name.endswith("SKILL.md") for name in archive.namelist())

    report = client.post("/api/chat/report", json={"state": done["state"]})
    assert report.status_code == 200
    assert "Pilot-led" in report.get_data(as_text=True)

    early = client.post("/api/chat/kit", json={"state": {}})
    assert early.status_code == 400
    assert early.get_json()["error"]["code"] == "not_ready"


def test_chat_page_and_health(client):
    health = client.get("/health")
    assert health.get_json()["status"] == "ok"
    page = client.get("/chat")
    assert page.status_code == 200
    assert b"AI Partner takes one consulting job" in page.data
    assert b"/api/chat" in page.data
    root = client.get("/")
    assert root.status_code == 302
    assert "/chat" in root.headers["Location"]


def test_rate_limit_is_per_chat(client):
    state = {}
    for _ in range(TURN_LIMIT):
        res = client.post("/api/chat", json={"message": "", "state": state})
        assert res.status_code == 200
        state = res.get_json()["state"]
    blocked = client.post("/api/chat", json={"message": "", "state": state})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "rate"
    other = client.post("/api/chat", json={"message": "", "state": {}})
    assert other.status_code == 200


def test_vercel_skips_sqlite_and_blocks_engagements(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    target = tmp_path / "data"
    monkeypatch.setattr(Config, "DATA_DIR", str(target))
    monkeypatch.setattr("server.api.chat.complete_with_venice", fake_model([]))
    from server import create_app

    app = create_app()
    http = app.test_client()
    res = http.post("/api/chat", json={"message": "Pricing for a B2B analytics product", "state": {}})
    assert res.status_code == 200
    blocked = http.get("/api/engagements")
    assert blocked.status_code == 503
    assert blocked.get_json()["error"]["code"] == "no_store"
    assert not target.exists()


def test_root_without_vercel_is_not_the_chat(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    res = create_app().test_client().get("/")
    assert res.status_code != 302


def test_railway_still_creates_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("VENICE_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    from server import create_app

    create_app()
    assert (tmp_path / "engagements.db").is_file()


def test_vercel_entrypoint_module():
    from api.index import app

    res = app.test_client().get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
    page = app.test_client().get("/chat")
    assert page.status_code == 200

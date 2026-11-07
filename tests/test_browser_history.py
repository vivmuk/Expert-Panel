"""Same-browser history is a local script. Two storage objects do not share rows."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_history_script_accepts_migration_isolation_and_bounds():
    node = shutil.which("node")
    assert node, "node is required to run tests/test_history.js"
    subprocess.check_call([node, str(ROOT / "tests" / "test_history.js")], cwd=ROOT)


def test_chat_page_exposes_the_project_list():
    from server import create_app

    client = create_app().test_client()
    page = client.get("/chat").get_data(as_text=True)
    assert 'id="projects"' in page
    assert 'id="history-note"' in page
    assert 'id="recover-storage"' in page
    assert 'src="/history.js"' in page
    script = client.get("/history.js")
    assert script.status_code == 200
    assert b"ai-partner-chat-v2" in script.data
    assert b"/api/engagements" not in script.data

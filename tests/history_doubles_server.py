"""Local /chat server for the browser history journey.

Uses the existing model and search doubles. It is not part of the pytest suite
and it does not call Venice, Exa, or Supermemory. POST /__test/hold pauses
POST /api/chat until released. GET /__test/done-state returns one finished job.
"""
import os
import threading

os.environ.setdefault("AI_PARTNER_SIGNING_SECRETS", "v1:test-signing-secret")
os.environ.setdefault("VENICE_API_KEY", "local-double")
os.environ["SUPERMEMORY_API_KEY"] = ""
os.environ.setdefault("VERCEL", "1")

from flask import jsonify, request

from server import create_app
from tests.test_chatjob import ONE_SHOT, fake_model
import server.api.chat as chat

GATE = threading.Event()
GATE.set()
CALLS = []


def build_done():
    chat.complete_with_venice = fake_model(CALLS)
    chat.exa_search = lambda query, limit=4: []
    client = create_app().test_client()
    body = client.post("/api/chat", json={"message": ONE_SHOT, "state": {}}).get_json()
    guard = 0
    while body.get("next") and guard < 30:
        guard += 1
        body = client.post("/api/chat", json={"message": "", "state": body["state"]}).get_json()
    body = client.post("/api/chat", json={"message": "small", "state": body["state"]}).get_json()
    while body.get("next") and guard < 40:
        guard += 1
        body = client.post("/api/chat", json={"message": "", "state": body["state"]}).get_json()
    return body["state"]


def main():
    done = build_done()
    app = create_app()
    chat.complete_with_venice = fake_model(CALLS)
    chat.exa_search = lambda query, limit=4: []

    @app.before_request
    def _pause_chat_when_held():
        if request.path == "/api/chat":
            GATE.wait(20)

    @app.post("/__test/hold")
    def _hold():
        body = request.get_json(silent=True) or {}
        if body.get("hold"):
            GATE.clear()
        else:
            GATE.set()
        return jsonify({"holding": not GATE.is_set()})

    @app.get("/__test/done-state")
    def _done():
        return jsonify(done)

    @app.post("/__test/reset")
    def _reset():
        chat.reset_limits()
        return jsonify({"ok": True})

    app.run(host="127.0.0.1", port=8766, threaded=True)


if __name__ == "__main__":
    main()

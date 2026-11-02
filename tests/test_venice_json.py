from server.venice.client import VeniceClient, _extract_json


def test_extract_json_strips_a_fence():
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_takes_the_outer_object_or_array():
    assert _extract_json('note {"a": 1} trailing') == {"a": 1}
    assert _extract_json("items [1, 2] done") == [1, 2]


class _Response:
    def __init__(self, content):
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}], "usage": {}}


def test_structured_output_asks_for_json_object_and_retries_once(monkeypatch):
    client = VeniceClient(api_key="test-not-a-real-key")
    seen = []

    def fake_request(method, path, json_body=None, **_kwargs):
        seen.append(json_body)
        if len(seen) == 1:
            return _Response("not json")
        return _Response('{"ok": true}')

    monkeypatch.setattr(client, "_request", fake_request)
    parsed = client.structured("deepseek-v4-1-flash-1017-uncensored", [{"role": "user", "content": "Hi"}], "Chat", {"type": "object"})
    assert parsed == {"ok": True}
    assert seen[0]["response_format"] == {"type": "json_object"}
    repair = seen[1]["messages"][-1]["content"]
    assert repair.startswith("Return valid JSON only. Parse error:")
    assert "No JSON found" in repair

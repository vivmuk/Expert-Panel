"""Per-customer Maritime provisioning with a fake API. No network."""
import io
import json
import zipfile

import pytest

from tools.maritime_provision import execute, main

VENICE = "vk-live-test-value"
MARITIME = "mk_live_test_value_xxxxxxxx"
SIGNING = "v1:sign-test-value-xxxx"


class Fake:
    def __init__(self):
        self.calls = []
        self.agents = []
        self.spend_status = 200
        self.cap = None
        self.uploaded = None

    def __call__(self, method, path, *, query=None, body=None, raw=None, content_type=None, api_key):
        self.calls.append({"method": method, "path": path, "body": body, "raw": raw, "query": query})
        assert api_key == MARITIME
        if method == "GET" and path == "/api/agents":
            external = (query or {}).get("externalId")
            matched = [agent for agent in self.agents if not external or agent["externalId"] == external]
            return 200, matched
        if method == "POST" and path == "/api/agents":
            if any(agent["externalId"] == body["externalId"] for agent in self.agents):
                return 409, {"error": "exists", "echo": body}
            agent = {
                "id": "agt_" + body["externalId"],
                "name": body["name"],
                "externalId": body["externalId"],
                "status": "deploying",
                "env": body.get("initialEnvVars"),
            }
            self.agents.append(agent)
            return 201, agent
        if method == "POST" and path.endswith("/env"):
            return 200, {"key": body["key"], "isSecret": body["isSecret"]}
        if method == "POST" and path.endswith("/reload-env"):
            return 200, {}
        if method == "PUT" and path.endswith("/llm-spend-limit"):
            self.cap = body
            if self.spend_status >= 400:
                return self.spend_status, {"error": "unsupported"}
            return 200, {"monthlyLimitCents": body["monthlyLimitCents"], "source": "agent"}
        if method == "GET" and path.endswith("/files/list"):
            return 200, {"root": "/data", "entries": []}
        if method == "POST" and path.endswith("/files/upload"):
            self.uploaded = raw
            return 200, {"ok": True, "path": "/data/kit.zip"}
        if method == "DELETE" and path.startswith("/api/agents/"):
            agent_id = path.rsplit("/", 1)[-1]
            before = len(self.agents)
            self.agents = [agent for agent in self.agents if agent["id"] != agent_id]
            if len(self.agents) == before:
                return 404, {"error": "missing"}
            return 204, None
        return 500, {"error": "unexpected"}


def _kit(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("skills/SKILL.md", "pilot kit")
    path = tmp_path / "kit.zip"
    path.write_bytes(buffer.getvalue())
    return str(path)


def _env(**extra):
    env = {
        "MARITIME_API_KEY": MARITIME,
        "VENICE_API_KEY": VENICE,
        "VENICE_BASE_URL": "https://api.venice.ai/api/v1",
        "AI_PARTNER_SIGNING_SECRETS": SIGNING,
    }
    env.update(extra)
    return env


def test_dry_run_makes_no_calls_and_hides_the_keys(tmp_path, capsys):
    def explode(**_kwargs):
        raise AssertionError("network")

    code = main(
        ["provision", "--external-id", "pilot_1", "--kit", _kit(tmp_path)],
        env=_env(),
        transport=explode,
        out=None,
    )
    printed = capsys.readouterr().out
    assert code == 0
    assert VENICE not in printed
    assert MARITIME not in printed
    plan = json.loads(printed)
    assert plan["dry_run"] is True
    assert plan["github_repo"] == "https://github.com/vivmuk/Expert-Panel"
    assert plan["framework"] == "custom"
    assert plan["env"] == ["VENICE_API_KEY", "VENICE_BASE_URL", "AI_PARTNER_SIGNING_SECRETS"]
    assert plan["venice_key"] == "set"
    assert plan["signing_secret"] == "set"
    assert SIGNING not in printed
    assert plan["spend_cap_cents"] is None


def test_apply_is_idempotent_and_uploads_the_kit(tmp_path):
    fake = Fake()
    env = _env(MARITIME_LLM_SPEND_CAP_CENTS="500")
    kit = _kit(tmp_path)
    first = execute(["provision", "--external-id", "pilot_1", "--kit", kit, "--apply"], env, fake)
    second = execute(["provision", "--external-id", "pilot_1", "--kit", kit, "--apply"], env, fake)
    assert first["created"] is True
    assert second["created"] is False
    assert first["id"] == second["id"] == "agt_pilot_1"
    assert first["kit_path"] == "/data/kit.zip"
    assert first["spend_cap_applied"] is True
    assert fake.cap == {"monthlyLimitCents": 500}
    creates = [call for call in fake.calls if call["method"] == "POST" and call["path"] == "/api/agents"]
    assert len(creates) == 1
    body = creates[0]["body"]
    assert body["githubRepo"] == "https://github.com/vivmuk/Expert-Panel"
    assert body["framework"] == "custom"
    assert body["branch"] == "master"
    assert body["externalId"] == "pilot_1"
    venice = [item for item in body["initialEnvVars"] if item["key"] == "VENICE_API_KEY"][0]
    assert venice["value"] == VENICE
    assert venice["isSecret"] is True
    signing = [item for item in body["initialEnvVars"] if item["key"] == "AI_PARTNER_SIGNING_SECRETS"][0]
    assert signing["value"] == SIGNING
    assert signing["isSecret"] is True
    assert "unit_amount" not in json.dumps(body)
    assert fake.uploaded is not None
    assert b"dest_dir" in fake.uploaded and b"/data" in fake.uploaded
    text = json.dumps(second)
    assert VENICE not in text
    assert MARITIME not in text
    assert SIGNING not in text
    listed = execute(["list", "--external-id", "pilot_1"], env, fake)
    assert listed["agents"] == [{
        "id": "agt_pilot_1",
        "name": first["name"],
        "externalId": "pilot_1",
        "status": "deploying",
    }]
    assert VENICE not in json.dumps(listed)
    dry = execute(["teardown", "--external-id", "pilot_1"], env, fake)
    assert dry["dry_run"] is True
    assert len(fake.agents) == 1
    gone = execute(["teardown", "--external-id", "pilot_1", "--apply"], env, fake)
    assert gone["deleted"] == ["agt_pilot_1"]
    again = execute(["teardown", "--external-id", "pilot_1", "--apply"], env, fake)
    assert again["deleted"] == []


def test_a_missing_spend_cap_endpoint_still_uploads(tmp_path):
    fake = Fake()
    fake.spend_status = 404
    result = execute(
        ["provision", "--external-id", "pilot_2", "--kit", _kit(tmp_path), "--apply"],
        _env(MARITIME_LLM_SPEND_CAP_CENTS="100"),
        fake,
    )
    assert result["spend_cap_applied"] is False
    assert result["kit_path"] == "/data/kit.zip"
    assert any(call["path"].endswith("/files/upload") for call in fake.calls)


def test_apply_without_a_key_does_not_call_and_does_not_print_one(tmp_path, capsys):
    def explode(**_kwargs):
        raise AssertionError("network")

    code = main(
        ["provision", "--external-id", "pilot_1", "--kit", _kit(tmp_path), "--apply"],
        env={"VENICE_API_KEY": VENICE},
        transport=explode,
        out=None,
    )
    printed = capsys.readouterr().out
    assert code == 2
    assert "Set MARITIME_API_KEY." in printed
    assert VENICE not in printed


def test_an_error_body_that_echoes_secrets_is_redacted(tmp_path, capsys):
    def leak(method, path, *, query=None, body=None, raw=None, content_type=None, api_key):
        return 500, {"error": api_key + " " + VENICE}

    code = main(
        ["list"],
        env=_env(),
        transport=leak,
        out=None,
    )
    printed = capsys.readouterr().out
    assert code == 2
    assert VENICE not in printed
    assert MARITIME not in printed
    assert "[redacted]" in printed


def test_bad_external_id_is_refused(tmp_path):
    with pytest.raises(Exception) as caught:
        execute(["provision", "--external-id", "has space", "--kit", _kit(tmp_path)], _env(), None)
    assert "externalId" in str(caught.value)

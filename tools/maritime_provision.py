"""Provision one Maritime agent per pilot customer.

The agent builds this repo's root Dockerfile, the same web app Maritime already
runs for AI Partner. Inference is Venice. The script reads MARITIME_API_KEY and
VENICE_API_KEY from the environment and does not print them.

Dry-run is the default. --apply performs the calls.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.maritime.sh"
DEFAULT_REPO = "https://github.com/vivmuk/Expert-Panel"
DEFAULT_BRANCH = "master"
DEFAULT_VENICE_BASE = "https://api.venice.ai/api/v1"
EXTERNAL_ID = re.compile(r"^[A-Za-z0-9_@.:+-]{1,128}$")
KIT_LIMIT = 100 * 1024 * 1024


class MaritimeError(RuntimeError):
    pass


def agent_name(external_id):
    slug = re.sub(r"[^a-z0-9]+", "-", external_id.lower()).strip("-") or "customer"
    digest = hashlib.sha256(external_id.encode()).hexdigest()[:8]
    return f"ai-partner-{slug[:32]}-{digest}"


def _secret(env, name):
    value = env.get(name, "")
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or any(ch.isspace() for ch in text):
        return ""
    return text


def spend_cap(env):
    raw = env.get("MARITIME_LLM_SPEND_CAP_CENTS", "")
    if not isinstance(raw, str):
        raw = ""
    raw = raw.strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise MaritimeError("MARITIME_LLM_SPEND_CAP_CENTS must be a whole number of cents.")
    value = int(raw)
    if value > 1_000_000:
        raise MaritimeError("MARITIME_LLM_SPEND_CAP_CENTS is above 1000000.")
    return value


def _redact(text, secrets):
    for secret in secrets:
        if secret and len(secret) >= 8:
            text = text.replace(secret, "[redacted]")
    return text


def urllib_transport(method, path, *, query=None, body=None, raw=None, content_type=None, api_key):
    url = API_ROOT + path
    pairs = {key: value for key, value in (query or {}).items() if value is not None}
    if pairs:
        url += "?" + urllib.parse.urlencode(pairs)
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    headers = {"Authorization": "Bearer " + api_key, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw_body = exc.read()
    if not raw_body:
        return status, None
    try:
        return status, json.loads(raw_body.decode())
    except json.JSONDecodeError:
        return status, raw_body.decode(errors="replace")


def _agents(payload):
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("agents", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("id"):
            return [payload]
    return []


def select_agents(payload, external_id):
    agents = _agents(payload)
    if external_id is None:
        return agents
    marked = [agent for agent in agents if "externalId" in agent or "external_id" in agent]
    if marked:
        return [
            agent
            for agent in marked
            if agent.get("externalId") == external_id or agent.get("external_id") == external_id
        ]
    return agents


def _public_agent(agent):
    return {
        "id": agent.get("id"),
        "name": agent.get("name"),
        "externalId": agent.get("externalId") or agent.get("external_id"),
        "status": agent.get("status"),
    }


class Client:
    def __init__(self, api_key, transport):
        self.api_key = api_key
        self.transport = transport

    def call(self, method, path, *, query=None, body=None, raw=None, content_type=None):
        status, payload = self.transport(
            method,
            path,
            query=query,
            body=body,
            raw=raw,
            content_type=content_type,
            api_key=self.api_key,
        )
        if status >= 400:
            detail = payload if isinstance(payload, str) else json.dumps(payload or {})
            raise MaritimeError(f"Maritime answered {status} for {method} {path}. {_redact(detail, [self.api_key])}")
        return payload

    def list_agents(self, external_id=None):
        payload = self.call("GET", "/api/agents", query={"externalId": external_id})
        return select_agents(payload, external_id)

    def create(self, body):
        try:
            payload = self.call("POST", "/api/agents", body=body)
        except MaritimeError as exc:
            if "answered 409" not in str(exc):
                raise
            found = self.list_agents(body["externalId"])
            if not found:
                raise
            return found[0]
        agents = _agents(payload)
        if not agents or not agents[0].get("id"):
            raise MaritimeError("Maritime did not return an agent id.")
        return agents[0]

    def set_env(self, agent_id, key, value, secret):
        self.call(
            "POST",
            f"/api/agents/{urllib.parse.quote(agent_id, safe='')}/env",
            body={"key": key, "value": value, "isSecret": secret},
        )

    def reload_env(self, agent_id):
        self.call("POST", f"/api/agents/{urllib.parse.quote(agent_id, safe='')}/reload-env")

    def set_spend_cap(self, agent_id, cents):
        path = f"/api/agents/{urllib.parse.quote(agent_id, safe='')}/llm-spend-limit"
        status, payload = self.transport(
            "PUT",
            path,
            query=None,
            body={"monthlyLimitCents": cents},
            raw=None,
            content_type=None,
            api_key=self.api_key,
        )
        if status in (404, 405):
            return False
        if status >= 400:
            raise MaritimeError(f"Maritime answered {status} for PUT {path}.")
        return payload

    def volume_root(self, agent_id):
        payload = self.call("GET", f"/api/agents/{urllib.parse.quote(agent_id, safe='')}/files/list")
        root = payload.get("root") if isinstance(payload, dict) else None
        if not isinstance(root, str) or not root.startswith("/"):
            raise MaritimeError("Maritime did not report a data volume root.")
        return root

    def upload(self, agent_id, filename, content, dest_dir):
        raw, content_type = _multipart({"dest_dir": dest_dir}, filename, content)
        self.call(
            "POST",
            f"/api/agents/{urllib.parse.quote(agent_id, safe='')}/files/upload",
            raw=raw,
            content_type=content_type,
        )

    def delete(self, agent_id):
        try:
            self.call("DELETE", f"/api/agents/{urllib.parse.quote(agent_id, safe='')}")
        except MaritimeError as exc:
            if "answered 404" not in str(exc):
                raise


def _multipart(fields, filename, content):
    boundary = "----ai-partner-kit"
    chunks = []
    for key, value in fields.items():
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), "multipart/form-data; boundary=" + boundary


def _read_kit(path):
    if not path or not os.path.isfile(path):
        raise MaritimeError("Pass --kit pointing at the customer's kit.zip.")
    with open(path, "rb") as handle:
        content = handle.read(KIT_LIMIT + 1)
    if len(content) > KIT_LIMIT:
        raise MaritimeError("The kit is over Maritime's 100 MB upload limit.")
    if not content.startswith(b"PK"):
        raise MaritimeError("The kit must be a zip file.")
    return content


def _spec(env, external_id, kit):
    if not EXTERNAL_ID.fullmatch(external_id or ""):
        raise MaritimeError("externalId must be 1 to 128 letters, digits, or _ @ . : + -.")
    repo = _secret(env, "AI_PARTNER_GITHUB_REPO") or DEFAULT_REPO
    branch = _secret(env, "AI_PARTNER_GITHUB_BRANCH") or DEFAULT_BRANCH
    return {
        "external_id": external_id,
        "name": agent_name(external_id),
        "github_repo": repo,
        "branch": branch,
        "framework": "custom",
        "kit": kit,
        "venice_key_state": "set" if _secret(env, "VENICE_API_KEY") else "missing",
        "venice_base": _secret(env, "VENICE_BASE_URL") or DEFAULT_VENICE_BASE,
        "spend_cap_cents": spend_cap(env),
    }


def _create_body(spec, venice_key):
    return {
        "name": spec["name"],
        "externalId": spec["external_id"],
        "githubRepo": spec["github_repo"],
        "branch": spec["branch"],
        "framework": "custom",
        "healthCheckPath": "/health",
        "initialEnvVars": [
            {"key": "VENICE_API_KEY", "value": venice_key, "isSecret": True},
            {"key": "VENICE_BASE_URL", "value": spec["venice_base"], "isSecret": False},
        ],
    }


def provision(env, external_id, kit, apply, transport=None):
    spec = _spec(env, external_id, kit)
    plan = {
        "action": "provision",
        "dry_run": not apply,
        "external_id": spec["external_id"],
        "name": spec["name"],
        "github_repo": spec["github_repo"],
        "branch": spec["branch"],
        "framework": spec["framework"],
        "env": ["VENICE_API_KEY", "VENICE_BASE_URL"],
        "venice_key": spec["venice_key_state"],
        "kit": kit,
        "spend_cap_cents": spec["spend_cap_cents"],
        "spend_cap_note": (
            "Maritime's per-agent proxy cap. It does not meter Venice."
            if spec["spend_cap_cents"] is not None
            else "Unset. No spend cap was sent."
        ),
    }
    content = _read_kit(kit)
    if not apply:
        plan["exit_code"] = 0
        return plan
    api_key = _secret(env, "MARITIME_API_KEY")
    venice_key = _secret(env, "VENICE_API_KEY")
    if not api_key:
        raise MaritimeError("Set MARITIME_API_KEY.")
    if not venice_key:
        raise MaritimeError("Set VENICE_API_KEY.")
    client = Client(api_key, transport or urllib_transport)
    found = client.list_agents(spec["external_id"])
    if found:
        agent = found[0]
        created = False
    else:
        agent = client.create(_create_body(spec, venice_key))
        created = True
    agent_id = agent["id"]
    client.set_env(agent_id, "VENICE_API_KEY", venice_key, True)
    client.set_env(agent_id, "VENICE_BASE_URL", spec["venice_base"], False)
    client.reload_env(agent_id)
    cap_applied = None
    if spec["spend_cap_cents"] is not None:
        cap_applied = client.set_spend_cap(agent_id, spec["spend_cap_cents"]) is not False
    root = client.volume_root(agent_id)
    client.upload(agent_id, "kit.zip", content, root)
    plan.update({
        "dry_run": False,
        "created": created,
        "id": agent_id,
        "kit_path": root.rstrip("/") + "/kit.zip",
        "spend_cap_applied": cap_applied,
        "exit_code": 0,
    })
    return plan


def list_agents(env, external_id, transport=None):
    if external_id and not EXTERNAL_ID.fullmatch(external_id):
        raise MaritimeError("externalId must be 1 to 128 letters, digits, or _ @ . : + -.")
    api_key = _secret(env, "MARITIME_API_KEY")
    if not api_key:
        raise MaritimeError("Set MARITIME_API_KEY.")
    client = Client(api_key, transport or urllib_transport)
    agents = client.list_agents(external_id)
    return {
        "action": "list",
        "dry_run": False,
        "agents": [_public_agent(agent) for agent in agents],
        "exit_code": 0,
    }


def teardown(env, external_id, apply, transport=None):
    if not EXTERNAL_ID.fullmatch(external_id or ""):
        raise MaritimeError("externalId must be 1 to 128 letters, digits, or _ @ . : + -.")
    if not apply:
        return {
            "action": "teardown",
            "dry_run": True,
            "external_id": external_id,
            "exit_code": 0,
        }
    api_key = _secret(env, "MARITIME_API_KEY")
    if not api_key:
        raise MaritimeError("Set MARITIME_API_KEY.")
    client = Client(api_key, transport or urllib_transport)
    deleted = []
    for agent in client.list_agents(external_id):
        client.delete(agent["id"])
        deleted.append(agent["id"])
    return {
        "action": "teardown",
        "dry_run": False,
        "external_id": external_id,
        "deleted": deleted,
        "exit_code": 0,
    }


def execute(argv, env, transport=None):
    parser = argparse.ArgumentParser(prog="maritime_provision")
    sub = parser.add_subparsers(dest="command", required=True)
    provision_cmd = sub.add_parser("provision")
    provision_cmd.add_argument("--external-id", required=True)
    provision_cmd.add_argument("--kit", required=True)
    provision_cmd.add_argument("--apply", action="store_true")
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--external-id")
    teardown_cmd = sub.add_parser("teardown")
    teardown_cmd.add_argument("--external-id", required=True)
    teardown_cmd.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "provision":
        return provision(env, args.external_id, args.kit, args.apply, transport)
    if args.command == "list":
        return list_agents(env, args.external_id, transport)
    return teardown(env, args.external_id, args.apply, transport)


def main(argv=None, env=None, transport=None, out=None):
    env = os.environ if env is None else env
    secrets = [_secret(env, name) for name in ("MARITIME_API_KEY", "VENICE_API_KEY", "STRIPE_SECRET_KEY")]
    try:
        result = execute(list(sys.argv[1:] if argv is None else argv), env, transport)
    except MaritimeError as exc:
        result = {"ok": False, "error": _redact(str(exc), secrets), "exit_code": 2}
    text = json.dumps(result, indent=2)
    if any(secret and len(secret) >= 8 and secret in text for secret in secrets):
        raise RuntimeError("refusing to print a secret")
    print(text, file=out or sys.stdout)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())

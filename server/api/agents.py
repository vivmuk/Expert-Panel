import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid

from flask import Blueprint, Response, jsonify, request, send_file

from .. import mcpjobs
from ..artifacts import ArtifactError, generate_artifact
from ..catalog import groups
from ..chatjob import handle_turn
from ..spendguard import SpendClosed
from ..chatmemory import recall, remember
from ..downloads import download_path, save_download
from ..harnesskit import build_kit_zip
from ..keys import signing_secret
from ..skillpack import build_pack_zip
from ..venice.errors import SPEND_LIMIT_REPLY, out_of_credit
from .access import origin_allowed, request_origin, require_partner_key
from .chat import complete_with_venice, exa_search, spend_block

bp = Blueprint("agents", __name__)
logger = logging.getLogger(__name__)

PROTOCOL = "2025-03-26"

_JOB = {
    "job_id": {"type": "string", "description": "The job_id from start_job. The server keeps the state; use this from chat agents."},
    "state": {"type": "object", "description": "The full job state, for clients that carry it themselves."},
}


def _job_tool(name, description, extra=None, required=()):
    return {
        "name": name,
        "description": description + " Pass job_id, or the full state.",
        "inputSchema": {
            "type": "object",
            "properties": {**(extra or {}), **_JOB},
            "required": list(required),
            "additionalProperties": False,
        },
    }


TOOLS = [
    {
        "name": "start_job",
        "description": (
            "Start a strategy engagement from the team's first message. Returns the reply, a job_id for the next calls, "
            "and the job state. Relay the reply to the user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    _job_tool(
        "chat_turn",
        "Continue a strategy engagement with the user's next message. Relay each reply. While the result has next set, "
        "call chat_turn again with an empty message. With job_id the result omits the state.",
        {"message": {"type": "string"}},
        ("message",),
    ),
    _job_tool("get_work_chart", "Return the work chart from the job."),
    _job_tool("get_kit", "Build the harness kit from the job and return a download URL."),
    {
        "name": "list_artifacts",
        "description": "List every engagement artifact type, grouped by the thesis task map.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    _job_tool(
        "generate_artifact",
        "Write one catalog artifact from the job. Returns markdown, and the updated state unless you passed job_id.",
        {"artifact_id": {"type": "string"}},
        ("artifact_id",),
    ),
    _job_tool("get_skill_pack", "Build the skill pack from the job and return a download URL."),
]


def _public_base():
    return request_origin()


def _turn(message, state):
    return handle_turn(state or {}, message or "", complete_with_venice, recall, remember, exa_search)


def _owner():
    header = request.headers.get("Authorization", "")
    return hashlib.sha256(header[7:].strip().encode()).hexdigest()


def _kept(result, job_id):
    """Store the state under job_id and answer without it, so the client never carries the state."""
    mcpjobs.save(_owner(), job_id, result.get("state") or {})
    return _ok({**{k: v for k, v in result.items() if k != "state"}, "job_id": job_id})


def _tool(name, arguments):
    arguments = arguments or {}
    job_id = arguments.get("job_id")
    state = arguments.get("state") or {}
    if job_id:
        state = mcpjobs.load(_owner(), job_id)
        if state is None:
            return _err("Unknown or expired job_id. Call start_job again.")
    if name == "start_job":
        seed = arguments.get("state") if isinstance(arguments.get("state"), dict) else {}
        result = _turn(arguments.get("message") or "", seed)
        job_id = mcpjobs.new_id()
        mcpjobs.save(_owner(), job_id, result.get("state") or {})
        return _ok({**result, "job_id": job_id})
    if name == "chat_turn":
        result = _turn(arguments.get("message") or "", state)
        return _kept(result, job_id) if job_id else _ok(result)
    if name == "get_work_chart":
        chart = state.get("chart") if isinstance(state, dict) else None
        if not chart:
            return _err("The work chart is not ready yet.")
        return _ok({"chart": chart})
    if name == "get_kit":
        return _zip(state, build_kit_zip)
    if name == "get_skill_pack":
        return _zip(state, build_pack_zip)
    if name == "list_artifacts":
        return _ok({"groups": groups()})
    if name == "generate_artifact":
        try:
            result = generate_artifact(state, arguments.get("artifact_id") or "", complete_with_venice)
        except ArtifactError as exc:
            return _err(str(exc))
        except SpendClosed as exc:
            return _err(exc.message)
        return _kept(result, job_id) if job_id else _ok(result)
    return _err(f"Unknown tool {name}.")


def _zip(state, builder):
    try:
        blob = builder(state)
    except ValueError as exc:
        return _err(str(exc) or "That file is not ready yet.")
    name = save_download(blob, ".zip")
    return _ok({"url": _public_base() + "/api/downloads/" + name})


def _ok(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}


def _err(message):
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _rpc(body):
    method = body.get("method")
    rpc_id = body.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "AI Partner", "version": "1.0.0"},
            },
        }
    if method and method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = body.get("params") or {}
        result = _tool(params.get("name"), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


MODELS = ("ai-partner", "ai-partner-full")
SPENDING_TOOLS = {"start_job", "chat_turn", "generate_artifact"}


def _gate_mcp_call(body):
    """Rate-limit and daily-cap the tools that call the model. Mutates a new chat id into the arguments."""
    if body.get("method") != "tools/call":
        return None
    params = body.get("params")
    if not isinstance(params, dict):
        params = {}
        body["params"] = params
    name = params.get("name")
    if name not in SPENDING_TOOLS:
        return None
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
        params["arguments"] = arguments
    state = arguments.get("state") if isinstance(arguments.get("state"), dict) else {}
    job_id = arguments.get("job_id")
    if job_id:
        loaded = mcpjobs.load(_owner(), job_id)
        if not isinstance(loaded, dict):
            return None
        state = loaded
    elif name == "start_job" or not (isinstance(state.get("chat_id"), str) and state.get("chat_id").strip()):
        state = {**state, "chat_id": uuid.uuid4().hex[:16]}
    code, message, chat_id = spend_block(state)
    if code:
        payload = {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32000, "message": message}}
        return Response(json.dumps(payload), status=429, mimetype="application/json")
    if not job_id:
        arguments["state"] = {"chat_id": chat_id} if name == "start_job" else {**state, "chat_id": chat_id}
    return None


def _completion(completion_id, model, created, result):
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["reply"]},
                "finish_reason": "stop",
            }
        ],
        "ai_partner_state": result["state"],
    }


def _sse(completion_id, model, result):
    created = int(time.time())
    opening = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": result["reply"]}, "finish_reason": None}],
    }
    closing = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(opening)}\n\n"
    yield f"data: {json.dumps(closing)}\n\n"
    yield "data: [DONE]\n\n"


_PROCESS_KEY = secrets.token_hex(32)


def _session_mac(session_id):
    key = signing_secret() or _PROCESS_KEY
    return hmac.new(key.encode(), f"mcp|{session_id}".encode(), hashlib.sha256).hexdigest()[:32]


def issue_session():
    session_id = uuid.uuid4().hex
    return f"{session_id}.{_session_mac(session_id)}"


def session_valid(sent):
    session_id, _, mac = sent.partition(".")
    return bool(session_id and mac) and hmac.compare_digest(mac, _session_mac(session_id))


def _session_headers(method):
    if method == "initialize":
        return {"Mcp-Session-Id": issue_session()}
    sent = request.headers.get("Mcp-Session-Id", "").strip()
    if sent:
        return {"Mcp-Session-Id": sent}
    return {}


@bp.route("/mcp", methods=["POST"])
def mcp():
    denied = require_partner_key()
    if denied:
        return denied
    if not origin_allowed():
        return jsonify({"error": {"code": "forbidden", "message": "Origin is not allowed."}}), 403
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Expected a JSON-RPC object."}}), 400
    sent = request.headers.get("Mcp-Session-Id", "").strip()
    if sent and body.get("method") != "initialize" and not session_valid(sent):
        return jsonify({"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32001, "message": "Unknown session. Send initialize again."}}), 404
    blocked = _gate_mcp_call(body)
    if blocked:
        return blocked
    try:
        payload = _rpc(body)
    except Exception as exc:
        logger.exception("mcp call failed")
        message = SPEND_LIMIT_REPLY if out_of_credit(exc) else f"AI Partner error: {exc.__class__.__name__}."
        payload = {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32000, "message": message},
        }
    headers = _session_headers(body.get("method"))
    if payload is None:
        return Response(status=202, headers=headers)
    return Response(json.dumps(payload), mimetype="application/json", headers=headers)


@bp.route("/mcp", methods=["GET", "DELETE"])
def mcp_other():
    denied = require_partner_key()
    if denied:
        return denied
    if not origin_allowed():
        return jsonify({"error": {"code": "forbidden", "message": "Origin is not allowed."}}), 403
    return Response(status=405, headers={"Allow": "POST"})


@bp.post("/v1/chat/completions")
def chat_completions():
    denied = require_partner_key()
    if denied:
        return denied
    raw_bytes = request.get_data(cache=True)
    body = request.get_json(force=True, silent=True)
    if raw_bytes.strip() and not isinstance(body, dict):
        return jsonify({"error": {"message": "Send a JSON object.", "type": "invalid_request_error"}}), 400
    body = body or {}
    messages = body.get("messages") or []
    user = ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            user = str(message.get("content") or "")
            break
    if not user.strip():
        return jsonify({"error": {"message": "messages must include a user turn.", "type": "invalid_request_error"}}), 400
    model = body.get("model") or "ai-partner"
    if model not in MODELS:
        return jsonify({"error": {"message": "model is not available.", "type": "invalid_request_error"}}), 400
    state = body.get("ai_partner_state") if isinstance(body.get("ai_partner_state"), dict) else {}
    if model == "ai-partner-full":
        state = dict(state)
        state["depth"] = "full"
    if not isinstance(state.get("chat_id"), str) or not state.get("chat_id").strip():
        state = dict(state)
        state["chat_id"] = uuid.uuid4().hex[:16]
    code, message, chat_id = spend_block(state)
    if code:
        return jsonify({"error": {"message": message, "type": code}}), 429
    state = {**state, "chat_id": chat_id}
    try:
        result = _turn(user, state)
    except Exception as exc:
        logger.exception("completion turn failed")
        if out_of_credit(exc):
            return jsonify({"error": {"message": SPEND_LIMIT_REPLY, "type": "spend_limit"}}), 503
        return jsonify({"error": {"message": "The model call failed. Send the message again.", "type": "model_error"}}), 502
    if (result.get("error") or {}).get("code") == "not_configured":
        return jsonify({"error": {"message": result["reply"], "type": "not_configured"}}), 503
    created = int(time.time())
    completion_id = "chatcmpl-" + uuid.uuid4().hex[:24]
    if body.get("stream") is True:
        return Response(_sse(completion_id, model, result), mimetype="text/event-stream")
    return jsonify(_completion(completion_id, model, created, result))


@bp.get("/v1/models")
def models():
    denied = require_partner_key()
    if denied:
        return denied
    return jsonify(
        {
            "object": "list",
            "data": [
                {"id": "ai-partner", "object": "model", "owned_by": "ai-partner"},
                {"id": "ai-partner-full", "object": "model", "owned_by": "ai-partner"},
            ],
        }
    )


@bp.get("/api/downloads/<name>")
def fetch_download(name):
    path = download_path(name)
    if not path:
        return jsonify({"error": {"code": "not_found", "message": "Download not found."}}), 404
    return send_file(path, mimetype="application/zip", as_attachment=True, download_name=name)

import json
import logging
import os
import time
import uuid

from flask import Blueprint, Response, jsonify, request, send_file

from ..artifacts import ArtifactError, generate_artifact
from ..catalog import groups
from ..chatjob import handle_turn
from ..chatmemory import recall, remember
from ..downloads import download_path, save_download
from ..harnesskit import build_kit_zip
from ..skillpack import build_pack_zip
from ..venice.errors import SPEND_LIMIT_REPLY, out_of_credit
from .access import origin_allowed, request_origin, require_partner_key
from .chat import complete_with_venice, exa_search

bp = Blueprint("agents", __name__)
logger = logging.getLogger(__name__)

PROTOCOL = "2025-03-26"

TOOLS = [
    {
        "name": "start_job",
        "description": "Start a consulting job from the client's first message. Returns the reply and the job state to send on the next call.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "chat_turn",
        "description": "Continue a consulting job. Pass the state returned by the previous call.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "state": {"type": "object"},
            },
            "required": ["message", "state"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_work_chart",
        "description": "Return the work chart stored in the job state.",
        "inputSchema": {
            "type": "object",
            "properties": {"state": {"type": "object"}},
            "required": ["state"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_kit",
        "description": "Build the harness kit from the job state and return a download URL.",
        "inputSchema": {
            "type": "object",
            "properties": {"state": {"type": "object"}},
            "required": ["state"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_artifacts",
        "description": "List every consulting artifact type, grouped by the thesis task map.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "generate_artifact",
        "description": "Write one catalog artifact from the job state. Returns markdown and the updated state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "state": {"type": "object"},
            },
            "required": ["artifact_id", "state"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_skill_pack",
        "description": "Build the skill pack from the job state and return a download URL.",
        "inputSchema": {
            "type": "object",
            "properties": {"state": {"type": "object"}},
            "required": ["state"],
            "additionalProperties": False,
        },
    },
]


def _public_base():
    return request_origin()


def _turn(message, state):
    return handle_turn(state or {}, message or "", complete_with_venice, recall, remember, exa_search)


def _tool(name, arguments):
    arguments = arguments or {}
    if name == "start_job":
        result = _turn(arguments.get("message") or "", {})
        return _ok(result)
    if name == "chat_turn":
        result = _turn(arguments.get("message") or "", arguments.get("state") or {})
        return _ok(result)
    if name == "get_work_chart":
        state = arguments.get("state") or {}
        chart = state.get("chart") if isinstance(state, dict) else None
        if not chart:
            return _err("The work chart is not ready yet.")
        return _ok({"chart": chart})
    if name == "get_kit":
        return _zip(arguments.get("state") or {}, build_kit_zip)
    if name == "get_skill_pack":
        return _zip(arguments.get("state") or {}, build_pack_zip)
    if name == "list_artifacts":
        return _ok({"groups": groups()})
    if name == "generate_artifact":
        try:
            result = generate_artifact(
                arguments.get("state") or {},
                arguments.get("artifact_id") or "",
                complete_with_venice,
            )
        except ArtifactError as exc:
            return _err(str(exc))
        return _ok(result)
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


def _session_headers(method):
    if method == "initialize":
        return {"Mcp-Session-Id": uuid.uuid4().hex}
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
    body = request.get_json(force=True, silent=True) or {}
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
    try:
        result = _turn(user, state)
    except Exception as exc:
        logger.exception("completion turn failed")
        if out_of_credit(exc):
            return jsonify({"error": {"message": SPEND_LIMIT_REPLY, "type": "spend_limit"}}), 503
        return jsonify({"error": {"message": "The model call failed. Send the message again.", "type": "model_error"}}), 502
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

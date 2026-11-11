"""Forward login and paid prompts from an unpaid host to the Railway backend.

The browser talks to Maritime or Vercel. This process does not open Postgres
and does not call a model. The session cookie is local to this host; the token
is sent to Railway on each forwarded call.
"""
from flask import Response, current_app, request

from .entitlement import SESSION_HEADER, session_token
from .hostrole import railway_backend_url
from .spendguard import CLOSED, SpendClosed


class BackendUnconfigured(Exception):
    pass


def _transport(method, path, data, headers, content_type):
    custom = current_app.config.get("RAILWAY_TRANSPORT")
    if custom is not None:
        return custom(method, path, data, headers, content_type)
    url = railway_backend_url()
    if not url:
        raise BackendUnconfigured()
    import requests

    outbound = dict(headers)
    if content_type:
        outbound["Content-Type"] = content_type
    response = requests.request(
        method,
        url + path,
        data=data,
        headers=outbound,
        timeout=120,
        allow_redirects=False,
    )
    return response.status_code, response.content, response.headers.get("Content-Type", "application/json")


def _path():
    path = request.path
    if request.query_string:
        path = path + "?" + request.query_string.decode()
    return path


def _error(code, status):
    import json

    return Response(
        json.dumps({"error": {"code": code, "message": CLOSED[code]}}),
        status=status,
        content_type="application/json",
    )


def forward_bytes(method, path, data, headers, content_type):
    try:
        status, body, response_type = _transport(method, path, data, headers, content_type)
    except BackendUnconfigured:
        return _error("backend_unconfigured", 503)
    except Exception:
        return _error("backend_unavailable", 503)
    return Response(body, status=status, content_type=response_type or "application/json")


def forward_current_request():
    headers = {}
    incoming = request.headers.get("Authorization", "")
    if incoming and not incoming.startswith("Bearer sess_"):
        headers["Authorization"] = incoming
    token = session_token()
    if token:
        headers[SESSION_HEADER] = token
    return forward_bytes(request.method, _path(), request.get_data(), headers, request.content_type)


def forward_admin(partner_key):
    return forward_bytes(
        request.method,
        _path(),
        request.get_data(),
        {"Authorization": "Bearer " + partner_key},
        request.content_type,
    )


def call_backend(method, path, payload):
    """JSON call used by the auth proxy. Returns (status, parsed object or None, raw)."""
    import json

    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    token = session_token()
    if token:
        headers[SESSION_HEADER] = token
    try:
        status, body, _content_type = _transport(method, path, raw, headers, "application/json")
    except BackendUnconfigured as exc:
        raise SpendClosed("backend_unconfigured") from exc
    except Exception as exc:
        raise SpendClosed("backend_unavailable") from exc
    try:
        parsed = json.loads(body.decode() or "null")
    except (UnicodeError, json.JSONDecodeError):
        parsed = None
    return status, parsed, body

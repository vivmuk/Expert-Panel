import hashlib
import hmac
import os
from urllib.parse import urlparse

from flask import jsonify, request

from ..keys import verify_key

UNAUTHORIZED = {"error": {"code": "unauthorized", "message": "invalid or missing API key"}}


def partner_keys():
    raw = os.environ.get("AI_PARTNER_API_KEYS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def listed_key(token):
    if not isinstance(token, str) or not token:
        return False
    presented = hashlib.sha256(token.encode()).digest()
    ok = False
    for key in partner_keys():
        ok = hmac.compare_digest(presented, hashlib.sha256(key.encode()).digest()) or ok
    return ok


def require_partner_key():
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""
    if listed_key(token) or verify_key(token):
        return None
    return jsonify(UNAUTHORIZED), 401


def allowed_origins():
    found = set()
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        found.add(base)
    for item in os.environ.get("AI_PARTNER_ORIGINS", "").split(","):
        item = item.strip().rstrip("/")
        if item:
            found.add(item)
    return found


def origin_allowed():
    origin = request.headers.get("Origin", "").strip()
    if not origin:
        return True
    if origin.rstrip("/") in allowed_origins():
        return True
    return urlparse(origin).netloc == request.host

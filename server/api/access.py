import os

from flask import jsonify, request


def partner_keys():
    raw = os.environ.get("AI_PARTNER_API_KEYS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def require_partner_key():
    keys = partner_keys()
    if not keys:
        return (
            jsonify(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "Set AI_PARTNER_API_KEYS to use this endpoint.",
                    }
                }
            ),
            401,
        )
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""
    if token not in keys:
        return (
            jsonify(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "The bearer token is not in AI_PARTNER_API_KEYS.",
                    }
                }
            ),
            401,
        )
    return None

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

PLANS = ("starter", "strategy", "harness")
KEY_TTL_SECONDS = 60 * 60 * 24 * 30


def signing_secrets():
    found = {}
    raw = os.environ.get("AI_PARTNER_SIGNING_SECRETS", "")
    for part in raw.split(","):
        if ":" not in part:
            continue
        kid, secret = part.split(":", 1)
        kid = kid.strip()
        secret = secret.strip()
        if kid and secret:
            found[kid] = secret
    single = os.environ.get("AI_PARTNER_SIGNING_SECRET", "").strip()
    if single and "v1" not in found:
        found["v1"] = single
    return found


def signing_secret():
    secrets = signing_secrets()
    if not secrets:
        return ""
    return secrets.get("v1") or next(iter(secrets.values()))


def mint_key(email, plan, now=None, ttl=KEY_TTL_SECONDS, kid=None):
    secret_map = signing_secrets()
    if not secret_map:
        raise RuntimeError("sign-ups paused")
    if plan not in PLANS:
        raise ValueError("unknown plan")
    kid = kid or ("v1" if "v1" in secret_map else next(iter(secret_map)))
    secret = secret_map.get(kid)
    if not secret:
        raise ValueError("unknown key id")
    issued = int(time.time() if now is None else now)
    payload = {
        "email": email,
        "exp": issued + int(ttl),
        "iat": issued,
        "jti": secrets.token_hex(8),
        "kid": kid,
        "plan": plan,
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return "ap_" + body + "." + sig


def verify_key(token, now=None):
    secrets = signing_secrets()
    if not secrets or not isinstance(token, str) or not token.startswith("ap_"):
        return None
    rest = token[3:]
    if rest.count(".") != 1:
        return None
    body, sig = rest.split(".", 1)
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    kid = payload.get("kid")
    secret = secrets.get(kid) if isinstance(kid, str) else None
    if not secret or payload.get("plan") not in PLANS or not payload.get("email"):
        return None
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, int):
        return None
    if exp < int(time.time() if now is None else now):
        return None
    expect = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expect, sig):
        return None
    return payload


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)

"""Email magic-link sign-in.

On Railway this stores the user and the session. On Maritime and Vercel it
forwards the same calls to Railway and keeps only the browser cookie.
The proxy signs the browser IP with the chat signing secret so Railway's
email limit follows that person, not the proxy's outbound address.
"""
import base64
import hashlib
import hmac
import threading
import time
from urllib.parse import quote

from flask import Blueprint, jsonify, redirect, request

from .. import mailer
from ..backend_proxy import call_backend
from ..entitlement import COOKIE, session_token
from ..get_started import valid_email
from ..hostrole import account_role
from ..keys import signing_secrets
from ..spendguard import CLOSED, SpendClosed
from .access import allowed_origins, request_origin

bp = Blueprint("auth", __name__)

_WINDOW = 3600
_LIMIT = 5
_lock = threading.Lock()
_hits = {}


def reset_limits():
    with _lock:
        _hits.clear()


def _allow(ip, now=None):
    now = time.time() if now is None else now
    with _lock:
        stamps = [stamp for stamp in _hits.get(ip, []) if now - stamp < _WINDOW]
        if len(stamps) >= _LIMIT:
            _hits[ip] = stamps
            return False
        _hits[ip] = stamps + [now]
        return True


CLIENT_HEADER = "X-AI-Partner-Client"
_PROOF_TTL = 600


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).rstrip(b"=").decode()


def _unb64(text):
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad).decode()


def sign_client_ip(ip, now=None):
    """HMAC the browser address so the authority can rate-limit that person."""
    if not isinstance(ip, str) or not ip or any(ch.isspace() for ch in ip) or len(ip) > 80:
        return ""
    secrets = signing_secrets()
    if not secrets:
        return ""
    kid = "v1" if "v1" in secrets else next(iter(secrets))
    secret = secrets[kid]
    stamp = str(int(time.time() if now is None else now))
    body = f"{kid}.{stamp}.{_b64(ip)}"
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + mac


def verified_client_ip(header, now=None):
    """Return the signed address, or '' when the proof is missing or forged."""
    secrets = signing_secrets()
    if not secrets or not isinstance(header, str):
        return ""
    parts = header.split(".")
    if len(parts) != 4:
        return ""
    kid, stamp, encoded, mac = parts
    secret = secrets.get(kid)
    if not secret or not stamp.isdigit():
        return ""
    age = int(time.time() if now is None else now) - int(stamp)
    if age < 0 or age > _PROOF_TTL:
        return ""
    try:
        ip = _unb64(encoded)
    except (ValueError, UnicodeError):
        return ""
    if not ip or any(ch.isspace() for ch in ip) or len(ip) > 80:
        return ""
    body = f"{kid}.{stamp}.{encoded}"
    expect = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, mac):
        return ""
    return ip

LINK_BASES = (
    "https://74da9def-954d-4df0-9234-04a7301c4740.mtm.sh",
)


def _link_allowed(base):
    text = (base or "").strip().rstrip("/")
    if not text or any(ch.isspace() for ch in text):
        return ""
    allowed = {item.rstrip("/") for item in allowed_origins()}
    allowed.update(item.rstrip("/") for item in LINK_BASES)
    origin = request_origin().rstrip("/")
    if origin:
        allowed.add(origin)
    if text not in allowed:
        return ""
    return text


def _cookie(response, token):
    response.set_cookie(
        COOKIE,
        token,
        max_age=14 * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/",
    )
    return response


def _clear_cookie(response):
    response.delete_cookie(COOKIE, path="/")
    return response


def _public_user(user):
    return {
        "email": user["email"],
        "questions_granted": user["questions_granted"],
        "questions_used": user["questions_used"],
        "questions_remaining": user["questions_remaining"],
    }


@bp.post("/api/auth/request")
def request_link():
    if account_role() != "authority":
        return _proxy_request()
    body = request.get_json(force=True, silent=True) or {}
    email = valid_email(body.get("email"))
    if not email:
        return jsonify({"error": {"code": "bad_request", "message": "Enter a valid email."}}), 400
    from .chat import client_ip

    signed = verified_client_ip(request.headers.get(CLIENT_HEADER, ""))
    if not _allow(signed or client_ip()):
        return jsonify({"error": {"code": "rate", "message": "Too many sign-in emails. Try again later."}}), 429
    base = _link_allowed(body.get("link_base") or request_origin())
    if not base:
        return jsonify({"error": {"code": "bad_request", "message": "This host cannot receive the sign-in link."}}), 400
    sender = mailer.get_mailer()
    if sender is None:
        return jsonify({
            "error": {
                "code": "mailer_unconfigured",
                "message": "Email sign-in is not configured on this server.",
            }
        }), 503
    from ..accounts import AccountsUnavailable, issue_magic_link

    try:
        token = issue_magic_link(email)
    except AccountsUnavailable:
        return jsonify({"error": {"code": "accounts_unavailable", "message": CLOSED["accounts_unavailable"]}}), 503
    link = base + "/api/auth/verify?token=" + quote(token)
    sender.send(
        email,
        "Sign in to AI Partner",
        "Use this link to sign in. It expires in 20 minutes and works once.\n\n" + link + "\n",
    )
    from ..usage import note_event

    note_event("email", email, "sign_up")
    return jsonify({"ok": True})


def _proxy_request():
    body = request.get_json(force=True, silent=True) or {}
    email = valid_email(body.get("email"))
    if not email:
        return jsonify({"error": {"code": "bad_request", "message": "Enter a valid email."}}), 400
    base = _link_allowed(request_origin())
    if not base:
        return jsonify({"error": {"code": "bad_request", "message": "This host cannot receive the sign-in link."}}), 400
    from .chat import client_ip

    ip = client_ip()
    proof = sign_client_ip(ip)
    headers = {CLIENT_HEADER: proof} if proof else {}
    if not proof and not _allow(ip):
        return jsonify({"error": {"code": "rate", "message": "Too many sign-in emails. Try again later."}}), 429
    try:
        status, parsed, raw = call_backend(
            "POST", "/api/auth/request", {"email": email, "link_base": base}, headers=headers
        )
    except SpendClosed as exc:
        return jsonify({"error": {"code": exc.code, "message": exc.message}}), 503
    if parsed is None:
        return jsonify({"error": {"code": "backend_unavailable", "message": CLOSED["backend_unavailable"]}}), 503
    return jsonify(parsed), status


@bp.post("/api/auth/verify")
def verify_json():
    """Exchange a magic token. Proxies call this. Browsers use GET."""
    if account_role() != "authority":
        return jsonify({"error": {"code": "paid_host_closed", "message": CLOSED["paid_host_closed"]}}), 403
    body = request.get_json(force=True, silent=True) or {}
    return _issue(body.get("token"), redirect_to=None)


@bp.get("/api/auth/verify")
def verify_browser():
    token = request.args.get("token", "")
    if account_role() != "authority":
        try:
            status, parsed, _raw = call_backend("POST", "/api/auth/verify", {"token": token})
        except SpendClosed as exc:
            return jsonify({"error": {"code": exc.code, "message": exc.message}}), 503
        if status != 200 or not isinstance(parsed, dict) or not parsed.get("session_token"):
            message = "This sign-in link is invalid or already used."
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
                message = parsed["error"].get("message") or message
            return jsonify({"error": {"code": "bad_request", "message": message}}), 400
        response = redirect("/chat")
        return _cookie(response, parsed["session_token"])
    return _issue(token, redirect_to="/chat")


def _issue(token, redirect_to):
    from ..accounts import AccountsUnavailable, consume_magic_link, user_for_session

    try:
        session = consume_magic_link(token)
    except AccountsUnavailable:
        return jsonify({"error": {"code": "accounts_unavailable", "message": CLOSED["accounts_unavailable"]}}), 503
    if not session:
        return jsonify({"error": {"code": "bad_request", "message": "This sign-in link is invalid or already used."}}), 400
    user = user_for_session(session)
    from ..usage import note_event

    note_event("email", user["email"], "sign_in")
    payload = {"ok": True, "session_token": session, **_public_user(user)}
    if redirect_to:
        response = redirect(redirect_to)
        return _cookie(response, session)
    response = jsonify(payload)
    return _cookie(response, session)


@bp.get("/api/auth/me")
def me():
    if account_role() != "authority":
        if not session_token():
            return jsonify({"error": {"code": "unauthorized", "message": "Sign in required."}}), 401
        try:
            status, parsed, _raw = call_backend("GET", "/api/auth/me", {})
        except SpendClosed as exc:
            return jsonify({"error": {"code": exc.code, "message": exc.message}}), 503
        if not isinstance(parsed, dict):
            return jsonify({"error": {"code": "backend_unavailable", "message": CLOSED["backend_unavailable"]}}), 503
        return jsonify(parsed), status
    from ..accounts import AccountsUnavailable

    try:
        user = _authority_user()
    except AccountsUnavailable:
        return jsonify({"error": {"code": "accounts_unavailable", "message": CLOSED["accounts_unavailable"]}}), 503
    if user is None:
        return jsonify({"error": {"code": "unauthorized", "message": "Sign in required."}}), 401
    return jsonify(_public_user(user))


def _authority_user():
    from ..entitlement import current_user

    return current_user()


@bp.post("/api/auth/logout")
def logout():
    if account_role() == "authority":
        from ..accounts import revoke_session

        token = session_token()
        if token:
            try:
                revoke_session(token)
            except Exception:
                pass
    else:
        try:
            call_backend("POST", "/api/auth/logout", {})
        except SpendClosed:
            pass
    response = jsonify({"ok": True})
    return _clear_cookie(response)


@bp.get("/auth.js")
def auth_js():
    import os

    from flask import send_from_directory

    static = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    return send_from_directory(static, "auth.js")

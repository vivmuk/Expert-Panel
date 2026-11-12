"""Which process may own accounts and call paid providers.

Railway is the account authority and the only paid sender. Maritime and Vercel
are unpaid UI proxies: they call the Railway backend for login, session,
entitlement, and usage. They do not open DATABASE_URL and they do not call a
provider themselves.
"""
import os
from urllib.parse import urlsplit

from flask import current_app, has_request_context

# Public origin already used by this app. A proxy uses it unless an operator
# sets AI_PARTNER_RAILWAY_BACKEND_URL. This is not a database address.
DEFAULT_RAILWAY_BACKEND = "https://ai-partner.up.railway.app"


def _railway_process():
    """The live Railway service also sets VERCEL=1. That flag does not demote it."""
    from .chat_send import RAILWAY_MARKERS, _present

    return any(_present(name) for name in RAILWAY_MARKERS)


def role_from_env():
    role = os.environ.get("AI_PARTNER_ACCOUNT_ROLE", "").strip().lower()
    if role in {"authority", "proxy"}:
        return role
    if _railway_process():
        return "authority"
    return "proxy"


def bind_app(app):
    """Freeze the role for this process. A later env change does not retarget it."""
    role = role_from_env()
    railway = _railway_process()
    app.config["ACCOUNT_ROLE"] = role
    # Paid sockets and the user database stay on the Railway authority process.
    app.config["PAID_SENDER"] = role == "authority" and railway
    app.config["DATABASE_ALLOWED"] = role == "authority" and railway


def _configured(name):
    if has_request_context() and name in current_app.config:
        return current_app.config[name]
    return None


def _env_authority():
    """Startup path, before a request exists. A proxy env never qualifies."""
    if os.environ.get("AI_PARTNER_ACCOUNT_ROLE", "").strip().lower() == "proxy":
        return False
    return _railway_process()


def account_role():
    found = _configured("ACCOUNT_ROLE")
    if found:
        return found
    return role_from_env()


def paid_sender():
    if has_request_context():
        return bool(current_app.config.get("PAID_SENDER"))
    return _env_authority()


def database_allowed():
    if has_request_context():
        return bool(current_app.config.get("DATABASE_ALLOWED"))
    return _env_authority()


def railway_backend_url():
    configured = os.environ.get("AI_PARTNER_RAILWAY_BACKEND_URL", "").strip().rstrip("/")
    if configured:
        return _public_backend(configured)
    if account_role() == "proxy":
        return DEFAULT_RAILWAY_BACKEND
    return ""


def _public_backend(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().strip("[]")
    if parts.scheme == "https" and host:
        return url
    if parts.scheme == "http" and host in {"127.0.0.1", "localhost"}:
        return url
    return ""

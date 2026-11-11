import logging
import mimetypes
import os

mimetypes.add_type("image/webp", ".webp")

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from .api.access import allowed_origins
from .config import Config, require_api_key
from .db import PersistentStoreUnavailable
from .keys import signing_secrets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "Content-Security-Policy": "frame-ancestors 'self'",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
# Four uploads at the chat's 500KB cap, base64-expanded, plus the job state.
MAX_BODY_BYTES = 4 * 1024 * 1024


def _wants_json():
    path = request.path or ""
    if path.startswith(("/api/", "/v1/", "/mcp", "/keiki")):
        return True
    return path == "/chat" and request.method == "POST"


def create_app():
    require_api_key()

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    # For hosts without an edge-set client header (see client_ip): trust only the hop our one proxy appended.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
    CORS(
        app,
        resources={
            r"/api/*": {"origins": sorted(allowed_origins()) or ["https://api.invalid"]},
            r"/mcp": {"origins": "*"},
            r"/v1/*": {"origins": "*"},
        },
    )

    if not signing_secrets():
        logger.error("AI_PARTNER_SIGNING_SECRETS is not set. /api/chat will answer 503 until it is.")

    if os.environ.get("VERCEL"):
        logger.info("VERCEL is set. Skipping SQLite. Chat jobs stay in the browser.")
    else:
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        if Config.DATA_DIR.startswith(os.getcwd()):
            logger.warning(
                "DATA_DIR=%s is inside the working directory; on Railway attach a volume "
                "and set DATA_DIR=/data or engagements will be lost on redeploy.",
                Config.DATA_DIR,
            )
        from .db import init_db

        init_db()

    from .hostrole import bind_app

    bind_app(app)

    from .api import register_blueprints

    register_blueprints(app)

    if app.config.get("DATABASE_ALLOWED"):
        try:
            from .accounts import ensure_schema

            ensure_schema()
        except Exception:
            logger.exception("user database is not ready")

    if os.environ.get("KEIKI_SELF_CHECK_URL") and os.environ.get("KEIKI_HARNESS_SIGNING_SECRET"):
        from .api.keiki import start_self_check

        start_self_check(os.environ["KEIKI_SELF_CHECK_URL"])

    @app.get("/health")
    def health():
        from .buildinfo import commit_sha, fingerprint

        return jsonify({"status": "ok", "sha": commit_sha(), "build": fingerprint()})

    @app.errorhandler(PersistentStoreUnavailable)
    def no_store(exc):
        return jsonify({"error": {"code": "no_store", "message": str(exc)}}), 503

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        message = "The request is too large."
        if _wants_json():
            return jsonify({"error": {"code": "too_large", "message": message}}), 413
        return message, 413, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc, HTTPException):
            return exc
        logger.exception("request failed")
        message = "Something went wrong. Try again."
        if _wants_json():
            return jsonify({"error": {"code": "error", "message": message}}), 500
        return message, 500, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(404)
    def not_found(_exc):
        if request.path.startswith(("/api/", "/v1/", "/mcp")):
            return jsonify({"error": {"code": "not_found", "message": "Not found."}}), 404
        from .api.pages import not_found_page

        return not_found_page(), 404, {"Content-Type": "text/html; charset=utf-8"}

    @app.after_request
    def security_headers(resp):
        for name, value in SECURITY_HEADERS.items():
            resp.headers.setdefault(name, value)
        return resp

    return app

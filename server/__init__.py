import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from .api.access import allowed_origins
from .config import Config, require_api_key
from .db import PersistentStoreUnavailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    require_api_key()

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(
        app,
        resources={
            r"/api/*": {"origins": sorted(allowed_origins()) or ["https://api.invalid"]},
            r"/mcp": {"origins": "*"},
            r"/v1/*": {"origins": "*"},
        },
    )

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

    from .api import register_blueprints

    register_blueprints(app)

    @app.get("/health")
    def health():
        sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("GIT_COMMIT") or ""
        return jsonify({"status": "ok", "sha": sha})

    @app.errorhandler(PersistentStoreUnavailable)
    def no_store(exc):
        return jsonify({"error": {"code": "no_store", "message": str(exc)}}), 503

    return app

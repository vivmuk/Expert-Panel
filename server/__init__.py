import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config, require_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    require_api_key()

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

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
        return jsonify({"status": "ok"})

    return app

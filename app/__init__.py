"""
app/__init__.py
─────────────────────────────────────────────────────────────────────────────
Application factory.

Usage:
    # CLI / wsgi.py
    from app import create_app
    app = create_app()                     # reads FLASK_ENV from environment
    app = create_app("testing")            # explicit override

    # pytest conftest.py
    from app import create_app
    app = create_app("testing")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask

from .config import config_by_name
from .extensions import cors, limiter


def create_app(env: str | None = None) -> Flask:
    """Create and configure a Flask application instance.

    Args:
        env: One of "development" | "production" | "testing".
             Falls back to the FLASK_ENV environment variable,
             then to "development".

    Returns:
        A fully configured Flask application.
    """
    env = env or os.getenv("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=False)

    # ── Configuration ───────────────────────────────────────────────────────
    config_class = config_by_name.get(env, config_by_name["development"])
    app.config.from_object(config_class)

    # ── Ensure temp upload dir exists ───────────────────────────────────────
    Path(app.config["UPLOAD_TEMP_DIR"]).mkdir(parents=True, exist_ok=True)

    # ── Extensions ──────────────────────────────────────────────────────────
    cors.init_app(app, origins=app.config["CORS_ORIGINS"])
    limiter.init_app(app)

    # ── Blueprints ──────────────────────────────────────────────────────────
    from .api.v1 import bp as api_v1_bp
    from .main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    # ── Logging ─────────────────────────────────────────────────────────────
    _configure_logging(app)

    app.logger.info(
        "MarkForge started",
        extra={"env": env, "debug": app.config["DEBUG"]},
    )

    return app


def _configure_logging(app: Flask) -> None:
    """Set up structured logging appropriate for the environment."""
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Quieten noisy libraries in production
    if not app.config.get("DEBUG"):
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
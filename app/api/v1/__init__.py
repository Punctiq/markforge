"""
app/api/v1/__init__.py
─────────────────────────────────────────────────────────────────────────────
Versioned API blueprint — all v1 routes are registered here.

Registered in create_app() with url_prefix="/api/v1", so:
    /api/v1/health
    /api/v1/convert
"""

from flask import Blueprint

bp = Blueprint("api_v1", __name__)

# Import routes *after* bp is created to avoid circular imports.
from . import convert, health  # noqa: E402, F401
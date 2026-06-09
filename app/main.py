"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
Blueprint pentru rute non-API (frontend).
Înregistrat în create_app() cu url_prefix="/".
"""

from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Servește aplicația frontend."""
    return render_template("index.html")
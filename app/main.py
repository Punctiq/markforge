"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
Blueprint pentru rute non-API (frontend).
Înregistrat în create_app() cu url_prefix="/".
"""

from flask import Blueprint, render_template

from .auth.guards import current_user, login_required_ui

bp = Blueprint("main", __name__)


@bp.get("/")
@login_required_ui
def index():
    """Servește aplicația frontend."""
    return render_template("index.html", user=current_user())

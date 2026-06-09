"""
app/api/v1/health.py
─────────────────────────────────────────────────────────────────────────────
GET /api/v1/health

Lightweight liveness probe — useful for Docker HEALTHCHECK, load balancers,
and uptime monitors. Returns 200 when the process is alive.

Extend with a readiness variant (/ready) once we add a database or cache.
"""

from flask import current_app, jsonify

from . import bp


@bp.get("/health")
def health() -> tuple:
    """Return process liveness and basic runtime info."""
    return (
        jsonify(
            {
                "status": "ok",
                "env": current_app.config.get("ENV", "unknown"),
            }
        ),
        200,
    )
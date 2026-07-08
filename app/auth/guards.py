"""Authentication guards for UI and API routes."""

from __future__ import annotations

from functools import wraps

from flask import current_app, jsonify, redirect, request, session, url_for


def auth_enabled() -> bool:
    return bool(current_app.config.get("AUTH_ENABLED", False))


def current_user() -> dict | None:
    user = session.get("user")
    return user if isinstance(user, dict) else None


def is_authenticated() -> bool:
    return current_user() is not None


def login_required_ui(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not auth_enabled() or is_authenticated():
            return view(*args, **kwargs)
        return redirect(url_for("auth.login", next=request.full_path))

    return wrapped


def login_required_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not auth_enabled() or is_authenticated():
            return view(*args, **kwargs)
        return jsonify({"error": "Authentication required."}), 401

    return wrapped

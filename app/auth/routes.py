"""Google OAuth / OpenID Connect routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from . import oauth
from .guards import auth_enabled, current_user, is_authenticated

bp = Blueprint("auth", __name__, url_prefix="/auth")


def allowed_emails() -> set[str]:
    raw = str(current_app.config.get("AUTH_ALLOWED_EMAILS", "") or "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _normalize_email(value: object) -> str:
    return str(value or "").strip().lower()


def _safe_next_url() -> str:
    next_url = request.args.get("next") or "/"
    if not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


def _fetch_google_userinfo() -> dict:
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") if isinstance(token, dict) else None
    if userinfo:
        return dict(userinfo)
    return dict(oauth.google.userinfo(token=token))


def _validate_userinfo(userinfo: dict) -> tuple[dict | None, str | None]:
    email = _normalize_email(userinfo.get("email"))
    if not email:
        return None, "Google account did not provide an email address."

    if userinfo.get("email_verified") is not True:
        return None, "Google account email is not verified."

    if email not in allowed_emails():
        return None, "Google account is not allowed for this MarkForge instance."

    return {
        "email": email,
        "name": str(userinfo.get("name") or "").strip(),
        "picture": str(userinfo.get("picture") or "").strip(),
    }, None


@bp.get("/login")
def login():
    if not auth_enabled():
        return redirect("/")

    if is_authenticated():
        return redirect("/")

    next_url = _safe_next_url()
    google_start_url = url_for("auth.google_start", next=next_url) if next_url != "/" else url_for("auth.google_start")
    return render_template("login.html", google_start_url=google_start_url)


@bp.get("/google/start")
def google_start():
    if not auth_enabled():
        return redirect("/")

    if is_authenticated():
        return redirect("/")

    session["auth_next"] = _safe_next_url()
    redirect_uri = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not redirect_uri:
        redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.get("/callback")
def callback():
    if not auth_enabled():
        return redirect("/")

    try:
        userinfo = _fetch_google_userinfo()
    except Exception as exc:
        current_app.logger.warning("Google OAuth callback failed: %s", exc.__class__.__name__)
        return jsonify({"error": "Google login failed."}), 401

    user, error = _validate_userinfo(userinfo)
    if error:
        current_app.logger.warning(
            "Rejected Google login for email: %s",
            _normalize_email(userinfo.get("email")) or "missing",
        )
        session.pop("user", None)
        return jsonify({"error": error}), 403

    next_url = session.pop("auth_next", None)
    session.clear()
    session["user"] = user
    return redirect(next_url or "/")


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login") if auth_enabled() else "/")


@bp.get("/me")
def me():
    user = current_user()
    if not auth_enabled():
        return jsonify({"authenticated": False, "auth_enabled": False}), 200
    if not user:
        return jsonify({"authenticated": False, "auth_enabled": True}), 200
    return jsonify({"authenticated": True, "auth_enabled": True, "user": user}), 200

from io import BytesIO

import pytest

from app import create_app


def make_app(auth_enabled=True, allowed="owner@example.com"):
    app = create_app("testing")
    app.config.update(
        AUTH_ENABLED=auth_enabled,
        AUTH_ALLOWED_EMAILS=allowed,
        SECRET_KEY="test-secret-key-that-is-long-enough-for-auth",
        TESTING=True,
    )
    return app


@pytest.fixture()
def auth_client():
    return make_app(auth_enabled=True).test_client()


def test_auth_disabled_keeps_current_behavior():
    client = make_app(auth_enabled=False).test_client()

    assert client.get("/").status_code == 200
    assert client.get("/auth/login").headers["Location"] == "/"
    response = client.post("/api/v1/convert", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_unauthenticated_index_redirects_to_login(auth_client):
    response = auth_client.get("/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_page_renders_for_unauthenticated_user(auth_client):
    response = auth_client.get("/auth/login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "MarkForge AI" in html
    assert "Continue with Google" in html
    assert 'type="password"' not in html
    assert "password" not in html.lower()


def test_continue_with_google_points_to_oauth_start(auth_client):
    response = auth_client.get("/auth/login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/auth/google/start"' in html


def test_continue_with_google_preserves_safe_next_url(auth_client):
    response = auth_client.get("/auth/login?next=/reports")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/auth/google/start?next=/reports"' in html


def test_google_start_stores_next_before_oauth_redirect(monkeypatch, auth_client):
    from app.auth import routes

    class FakeGoogle:
        def authorize_redirect(self, redirect_uri):
            from flask import redirect

            return redirect(redirect_uri)

    monkeypatch.setattr(routes.oauth, "google", FakeGoogle(), raising=False)

    response = auth_client.get("/auth/google/start?next=/reports")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/callback")
    with auth_client.session_transaction() as session:
        assert session["auth_next"] == "/reports"


def test_authenticated_login_redirects_to_index(auth_client):
    with auth_client.session_transaction() as session:
        session["user"] = {"email": "owner@example.com", "name": "Owner", "picture": ""}

    response = auth_client.get("/auth/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_unauthenticated_convert_returns_401_json(auth_client):
    response = auth_client.post(
        "/api/v1/convert",
        data={"file": (BytesIO(b"hi"), "file.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required."


def test_unauthenticated_ai_status_returns_401_json(auth_client):
    response = auth_client.get("/api/v1/ai/status")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required."


def test_health_remains_public(auth_client):
    response = auth_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_auth_me_returns_false_when_not_logged_in(auth_client):
    response = auth_client.get("/auth/me")

    assert response.status_code == 200
    assert response.get_json() == {"authenticated": False, "auth_enabled": True}


def test_authenticated_index_and_ai_status_are_accessible(auth_client):
    with auth_client.session_transaction() as session:
        session["user"] = {"email": "owner@example.com", "name": "Owner", "picture": ""}

    index_response = auth_client.get("/")
    status_response = auth_client.get("/api/v1/ai/status")

    assert index_response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.get_json()["supported_modes"] == ["safe", "balanced", "aggressive"]


def test_auth_me_returns_user_when_logged_in(auth_client):
    user = {"email": "owner@example.com", "name": "Owner", "picture": ""}
    with auth_client.session_transaction() as session:
        session["user"] = user

    response = auth_client.get("/auth/me")

    assert response.status_code == 200
    assert response.get_json() == {
        "authenticated": True,
        "auth_enabled": True,
        "user": user,
    }


def test_allowed_email_session_works(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {
            "email": " Owner@Example.com ",
            "email_verified": True,
            "name": "Owner",
            "picture": "https://example.com/avatar.png",
        },
    )

    response = auth_client.get("/auth/callback")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with auth_client.session_transaction() as session:
        assert session["user"] == {
            "email": "owner@example.com",
            "name": "Owner",
            "picture": "https://example.com/avatar.png",
        }


def test_disallowed_email_renders_access_denied_page(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email": "intruder@example.com", "email_verified": True},
    )

    response = auth_client.get("/auth/callback")
    html = response.get_data(as_text=True)

    assert response.status_code == 403
    assert response.content_type.startswith("text/html")
    assert "Access denied" in html
    assert "Back to sign in" in html
    assert "intruder@example.com" not in html
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_missing_email_renders_access_denied_page(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email_verified": True},
    )

    response = auth_client.get("/auth/callback")
    html = response.get_data(as_text=True)

    assert response.status_code == 403
    assert "Access denied" in html
    assert "email address" not in html
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_unverified_email_renders_access_denied_page(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email": "owner@example.com", "email_verified": False},
    )

    response = auth_client.get("/auth/callback")
    html = response.get_data(as_text=True)

    assert response.status_code == 403
    assert "Access denied" in html
    assert "not verified" not in html
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_oauth_provider_exception_renders_safe_access_denied_page(monkeypatch, auth_client):
    from app.auth import routes

    def raise_provider_error():
        raise RuntimeError("raw provider failure with client_secret=oauth-secret")

    monkeypatch.setattr(routes, "_fetch_google_userinfo", raise_provider_error)

    response = auth_client.get("/auth/callback")
    html = response.get_data(as_text=True)

    assert response.status_code == 401
    assert "Access denied" in html
    assert "Back to sign in" in html
    assert "client_secret" not in html
    assert "oauth-secret" not in html
    assert "raw provider failure" not in html
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_logout_clears_session(auth_client):
    with auth_client.session_transaction() as session:
        session["user"] = {"email": "owner@example.com", "name": "Owner", "picture": ""}

    response = auth_client.get("/auth/logout")

    assert response.status_code == 302
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_auth_config_rejects_unsafe_secret():
    from flask import Flask

    from app import _validate_auth_config

    app = Flask(__name__)
    app.config.update(AUTH_ENABLED=True, SECRET_KEY="dev-secret-change-in-prod")

    with pytest.raises(RuntimeError):
        _validate_auth_config(app)

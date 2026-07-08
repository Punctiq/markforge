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
    response = client.post("/api/v1/convert", data={}, content_type="multipart/form-data")
    assert response.status_code == 400


def test_unauthenticated_index_redirects_to_login(auth_client):
    response = auth_client.get("/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


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


def test_disallowed_email_is_rejected(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email": "intruder@example.com", "email_verified": True},
    )

    response = auth_client.get("/auth/callback")

    assert response.status_code == 403
    assert "not allowed" in response.get_json()["error"]
    with auth_client.session_transaction() as session:
        assert "user" not in session



def test_missing_email_is_rejected(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email_verified": True},
    )

    response = auth_client.get("/auth/callback")

    assert response.status_code == 403
    assert "email address" in response.get_json()["error"]
    with auth_client.session_transaction() as session:
        assert "user" not in session


def test_unverified_email_is_rejected(monkeypatch, auth_client):
    from app.auth import routes

    monkeypatch.setattr(
        routes,
        "_fetch_google_userinfo",
        lambda: {"email": "owner@example.com", "email_verified": False},
    )

    response = auth_client.get("/auth/callback")

    assert response.status_code == 403
    assert "not verified" in response.get_json()["error"]
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

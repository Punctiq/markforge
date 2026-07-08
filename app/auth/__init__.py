"""Authentication helpers and routes for personal-use MarkForge."""

from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_oauth(app):
    """Register the Google OpenID Connect client."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

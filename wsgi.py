"""
wsgi.py
─────────────────────────────────────────────────────────────────────────────
WSGI entrypoint for production servers (gunicorn, uWSGI).

Usage:
    gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000

The module-level `app` variable is what WSGI servers look for by convention.
"""

from app import create_app

app = create_app()
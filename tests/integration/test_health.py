"""
tests/integration/test_health.py
─────────────────────────────────────────────────────────────────────────────
Integration test for GET /api/v1/health.
Spins up the full Flask app in test mode.
"""


def test_health_returns_200(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_ok_status(client):
    data = client.get("/api/v1/health").get_json()
    assert data["status"] == "ok"
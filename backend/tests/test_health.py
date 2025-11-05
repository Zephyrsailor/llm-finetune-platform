"""Basic health check test to validate application skeleton."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_ok() -> None:
    """Service should respond with an OK payload."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

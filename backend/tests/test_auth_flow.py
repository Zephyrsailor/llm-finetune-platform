"""Integration tests for authentication HTTP endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models import AuditLog, RefreshToken, User, VerificationCode


@pytest.fixture()
def client():
    """Provide a TestClient backed by an in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override_session():
        with Session(engine) as session:
            yield session

    original_environment = settings.environment
    settings.environment = "development"
    app.dependency_overrides[get_session] = _override_session
    test_client = TestClient(app)
    try:
        yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        settings.environment = original_environment
        SQLModel.metadata.drop_all(engine)


def test_registration_login_and_audit_logs(client):
    test_client, engine = client
    response = test_client.post("/api/v1/auth/register/request", json={"email": "user@example.com"})
    assert response.status_code == 200
    code = response.json()["verification_code"]

    confirm_payload = {"email": "user@example.com", "password": "Password123", "code": code}
    response = test_client.post("/api/v1/auth/register/confirm", json=confirm_payload)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens

    login_payload = {"email": "user@example.com", "password": "Password123"}
    response = test_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "user@example.com")).first()
        assert user is not None
        assert user.last_login_at is not None
        log = session.exec(select(AuditLog).where(AuditLog.event_type == "auth.login.success")).first()
        assert log is not None


def test_password_reset_revokes_tokens(client):
    test_client, engine = client
    code = test_client.post("/api/v1/auth/register/request", json={"email": "reset@example.com"}).json()[
        "verification_code"
    ]
    test_client.post(
        "/api/v1/auth/register/confirm",
        json={"email": "reset@example.com", "password": "Password123", "code": code},
    )
    refresh_token = test_client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "Password123"},
    ).json()["refresh_token"]

    reset_code = test_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset@example.com"}
    ).json()["verification_code"]
    confirm_payload = {
        "email": "reset@example.com",
        "code": reset_code,
        "new_password": "NewPassword456",
    }
    response = test_client.post("/api/v1/auth/password-reset/confirm", json=confirm_payload)
    assert response.status_code == 200

    response = test_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401

    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "NewPassword456"},
    )
    assert response.status_code == 200


def test_logout_and_refresh_flow(client):
    test_client, engine = client
    code = test_client.post("/api/v1/auth/register/request", json={"email": "session@example.com"}).json()[
        "verification_code"
    ]
    confirm_payload = {
        "email": "session@example.com",
        "password": "Password123",
        "code": code,
    }
    test_client.post("/api/v1/auth/register/confirm", json=confirm_payload)
    login_tokens = test_client.post(
        "/api/v1/auth/login",
        json={"email": "session@example.com", "password": "Password123"},
    ).json()

    refresh_response = test_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login_tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()

    logout_response = test_client.post(
        "/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert logout_response.status_code == 200

    response = test_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert response.status_code == 401

    with Session(engine) as session:
        revoked_count = session.exec(
            select(RefreshToken).where(RefreshToken.revoked.is_(True))
        ).all()
        assert len(revoked_count) >= 1


def test_registration_verification_attempt_limit(client):
    test_client, engine = client
    email = "limit@example.com"
    response = test_client.post("/api/v1/auth/register/request", json={"email": email})
    assert response.status_code == 200
    code = response.json()["verification_code"]

    wrong_payload = {
        "email": email,
        "password": "Password123",
        "code": "000000",
    }

    for _ in range(settings.verification_attempt_limit):
        resp = test_client.post("/api/v1/auth/register/confirm", json=wrong_payload)
        assert resp.status_code == 400

    with Session(engine) as session:
        remaining = session.exec(
            select(VerificationCode).where(
                VerificationCode.email == email,
                VerificationCode.purpose == "register",
            )
        ).all()
        assert len(remaining) == 0

    # Even with the original correct code the registration should now fail until用户重新请求验证码
    final_response = test_client.post(
        "/api/v1/auth/register/confirm",
        json={"email": email, "password": "Password123", "code": code},
    )
    assert final_response.status_code == 400

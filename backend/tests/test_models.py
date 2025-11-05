"""Model metadata smoke tests."""

from sqlmodel import SQLModel

from app.models import AuditLog, RefreshToken, User, VerificationCode


def test_models_registered_with_metadata() -> None:
    """All core models should be part of SQLModel metadata."""
    tables = SQLModel.metadata.tables
    assert User.__tablename__ in tables
    assert AuditLog.__tablename__ in tables
    assert RefreshToken.__tablename__ in tables
    assert VerificationCode.__tablename__ in tables

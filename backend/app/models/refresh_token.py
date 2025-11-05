"""Refresh token persistence model."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    """Track refresh tokens for revocation and audit."""

    __tablename__ = "refresh_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token_id: str = Field(max_length=128, unique=True, index=True)
    expires_at: datetime = Field(index=True)
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

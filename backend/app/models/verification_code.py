"""One-time verification code model."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class VerificationCode(SQLModel, table=True):
    """Verification code for email confirmation and password reset."""

    __tablename__ = "verification_codes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    email: str = Field(max_length=255, index=True)
    code: str = Field(max_length=64, index=True)
    purpose: str = Field(max_length=32)
    expire_at: datetime = Field(index=True)
    attempt_limit: int = Field(default=5)
    attempts_made: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

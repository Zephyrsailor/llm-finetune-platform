"""Authentication API schemas."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import TokenPair


class RegistrationRequest(BaseModel):
    """Payload for requesting registration verification."""

    email: EmailStr


class RegistrationConfirmRequest(BaseModel):
    """Payload for confirming user registration."""

    email: EmailStr
    password: str = Field(min_length=8)
    code: str = Field(min_length=4)


class LoginRequest(BaseModel):
    """Credential payload for login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Payload for refreshing token pair."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Payload for logging out."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Payload for requesting a password reset code."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Payload for confirming password reset."""

    email: EmailStr
    code: str = Field(min_length=4)
    new_password: str = Field(min_length=8)


class VerificationResponse(BaseModel):
    """Message returned after sending verification codes."""

    message: str
    verification_code: str | None = None


class MessageResponse(BaseModel):
    """Simple status message."""

    message: str


class LoginResponse(TokenPair):
    """Alias for token pair responses."""

    pass

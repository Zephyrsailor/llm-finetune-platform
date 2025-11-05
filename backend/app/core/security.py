"""Security utilities for authentication workflows."""

from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Any, TypedDict
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return hashed representation of the supplied password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Validate a plaintext password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    """Create a signed JWT with the provided payload and expiry window."""
    payload = data.copy()
    expire = datetime.utcnow() + expires_delta
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class TokenPayload(TypedDict):
    """Structure of issued JWT payload."""

    sub: str
    scope: str
    jti: str
    exp: int


def generate_token_id() -> str:
    """Create a unique token identifier."""
    return uuid4().hex


def decode_token(token: str) -> TokenPayload:
    """Decode a JWT and return its payload."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload  # type: ignore[return-value]
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def generate_api_key() -> str:
    """Generate a random API key string."""
    return token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hash_password(api_key)


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify a plaintext API key against stored hash."""
    return verify_password(api_key, hashed)

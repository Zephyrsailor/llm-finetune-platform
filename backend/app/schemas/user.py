"""User related request and response schemas."""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(min_length=8)


class TokenPair(BaseModel):
    """Schema representing access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"

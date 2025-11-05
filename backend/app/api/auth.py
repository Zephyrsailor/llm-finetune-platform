"""Authentication API endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.rate_limit import InMemoryRateLimiter
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegistrationConfirmRequest,
    RegistrationRequest,
    VerificationResponse,
)
from app.services.auth import AuthService
from app.services.errors import AuthenticationError, RateLimitExceeded, VerificationError

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_login_limiter = InMemoryRateLimiter(
    max_attempts=settings.login_rate_limit_attempts,
    window=timedelta(seconds=settings.login_rate_limit_window_seconds),
)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """Dependency wiring for AuthService."""
    return AuthService(session=session, limiter=_login_limiter)


@router.post("/register/request", response_model=VerificationResponse)
def request_registration(payload: RegistrationRequest, service: AuthService = Depends(get_auth_service)) -> VerificationResponse:
    """Send a verification code for new user registration."""
    try:
        code = service.request_registration(email=payload.email)
    except VerificationError as exc:  # pragma: no cover - explicit error mapping
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return VerificationResponse(
        message="验证码已发送至邮箱",
        verification_code=code if settings.environment != "production" else None,
    )


@router.post("/register/confirm", response_model=LoginResponse)
def confirm_registration(
    payload: RegistrationConfirmRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """Confirm registration and create user credentials."""
    try:
        tokens = service.confirm_registration(
            email=payload.email,
            password=payload.password,
            code=payload.code,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except VerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LoginResponse(**tokens.model_dump())


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    """Authenticate with email/password credentials."""
    try:
        tokens = service.authenticate(
            email=payload.email,
            password=payload.password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except RateLimitExceeded as exc:  # pragma: no cover - rate limit branch
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(**tokens.model_dump())


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest, service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    """Issue new token pair using a refresh token."""
    try:
        tokens = service.refresh_tokens(payload.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(**tokens.model_dump())


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, service: AuthService = Depends(get_auth_service)) -> MessageResponse:
    """Revoke refresh token and end session."""
    try:
        service.logout(payload.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return MessageResponse(message="已退出登录")


@router.post("/password-reset/request", response_model=VerificationResponse)
def password_reset_request(payload: PasswordResetRequest, service: AuthService = Depends(get_auth_service)) -> VerificationResponse:
    """Send password reset verification code to user email."""
    code = service.request_password_reset(payload.email)
    return VerificationResponse(
        message="如果邮箱已注册，我们已发送验证码",
        verification_code=code if (code and settings.environment != "production") else None,
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def password_reset_confirm(payload: PasswordResetConfirmRequest, service: AuthService = Depends(get_auth_service)) -> MessageResponse:
    """Confirm password reset using verification code."""
    try:
        service.confirm_password_reset(email=payload.email, code=payload.code, new_password=payload.new_password)
    except VerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="密码已重置")

"""Authentication service implementation."""

from datetime import datetime, timedelta
import secrets
from typing import Any

from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter
from app.models import User
from app.repositories.audit import AuditLogRepository
from app.repositories.token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.repositories.verification import VerificationCodeRepository
from app.schemas.user import TokenPair
from app.services.errors import AuthenticationError, RateLimitExceeded, VerificationError

VERIFICATION_PURPOSE_REGISTER = "register"
VERIFICATION_PURPOSE_RESET = "password_reset"


class AuthService:
    """Provide high-level authentication actions."""

    def __init__(self, session: Session, limiter: InMemoryRateLimiter):
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._audits = AuditLogRepository(session)
        self._verifications = VerificationCodeRepository(session)
        self._limiter = limiter

    # Registration ----------------------------------------------------------------

    def request_registration(self, *, email: str) -> str:
        """Generate verification code for new user registration."""
        if self._users.exists(email):
            raise VerificationError("邮箱已注册")
        code = self._generate_code()
        expire_at = datetime.utcnow() + timedelta(minutes=settings.verification_code_expire_minutes)
        self._verifications.create(
            email=email,
            code=code,
            purpose=VERIFICATION_PURPOSE_REGISTER,
            expire_at=expire_at,
            attempt_limit=settings.verification_attempt_limit,
        )
        return code

    def confirm_registration(
        self,
        *,
        email: str,
        password: str,
        code: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        """Create user after verifying registration code."""
        if self._users.exists(email):
            raise VerificationError("邮箱已注册")
        record = self._validate_verification_code(
            email=email,
            purpose=VERIFICATION_PURPOSE_REGISTER,
            provided_code=code,
        )
        hashed_password = security.hash_password(password)
        user = self._users.create(email=email, password_hash=hashed_password)
        self._verifications.delete(record)
        tokens = self._issue_tokens(user)
        self._audits.record(
            event_type="auth.registration.success",
            user_id=user.id,
            ip_address=ip,
            user_agent=user_agent,
            payload={"email": email},
        )
        return tokens

    # Login ------------------------------------------------------------------------

    def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        """Validate credentials and issue new token pair."""
        limiter_keys = self._limiter_keys(email=email, ip=ip)
        if any(not self._limiter.check(key) for key in limiter_keys):
            self._audits.record(
                event_type="auth.login.rate_limited",
                user_id=None,
                ip_address=ip,
                user_agent=user_agent,
                payload={"email": email},
            )
            raise RateLimitExceeded("尝试次数过多，请稍后再试")

        user = self._users.get_by_email(email)
        if user is None or not security.verify_password(password, user.password_hash):
            self._audits.record(
                event_type="auth.login.failure",
                user_id=user.id if user else None,
                ip_address=ip,
                user_agent=user_agent,
                payload={"reason": "invalid_credentials"},
            )
            raise AuthenticationError("邮箱或密码错误")

        tokens = self._issue_tokens(user)
        self._users.update_last_login(user)
        self._audits.record(
            event_type="auth.login.success",
            user_id=user.id,
            ip_address=ip,
            user_agent=user_agent,
            payload={},
        )
        for key in limiter_keys:
            self._limiter.reset(key)
        return tokens

    # Refresh / Logout -------------------------------------------------------------

    def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Issue a new token pair from a refresh token."""
        user, token_record = self._validate_refresh_token(refresh_token)
        tokens = self._issue_tokens(user)
        self._refresh_tokens.revoke(token_record.token_id)
        return tokens

    def logout(self, refresh_token: str) -> None:
        """Revoke refresh token to terminate session."""
        _, token_record = self._validate_refresh_token(refresh_token)
        self._refresh_tokens.revoke(token_record.token_id)

    # Password Reset ---------------------------------------------------------------

    def request_password_reset(self, email: str) -> str | None:
        """Generate verification code for password reset. Returns code (dev helper)."""
        user = self._users.get_by_email(email)
        if user is None:
            return None
        code = self._generate_code()
        expire_at = datetime.utcnow() + timedelta(minutes=settings.verification_code_expire_minutes)
        self._verifications.create(
            email=email,
            code=code,
            purpose=VERIFICATION_PURPOSE_RESET,
            expire_at=expire_at,
            user_id=user.id,
            attempt_limit=settings.verification_attempt_limit,
        )
        return code

    def confirm_password_reset(self, *, email: str, code: str, new_password: str) -> None:
        """Validate reset code and update the user password."""
        user = self._users.get_by_email(email)
        if user is None:
            raise VerificationError("验证码无效或已过期")
        record = self._validate_verification_code(
            email=email,
            purpose=VERIFICATION_PURPOSE_RESET,
            provided_code=code,
        )
        hashed_password = security.hash_password(new_password)
        self._users.update_password(user, hashed_password)
        self._refresh_tokens.revoke_all_for_user(user.id)
        self._verifications.delete(record)

    # Helpers ----------------------------------------------------------------------

    def _validate_verification_code(self, *, email: str, purpose: str, provided_code: str):
        """Ensure verification code exists and enforce attempt limits."""
        record = self._verifications.get_latest(email=email, purpose=purpose)
        if record is None:
            raise VerificationError("验证码无效或已过期")
        if record.attempts_made >= record.attempt_limit:
            self._verifications.delete(record)
            raise VerificationError("验证码无效或已过期")
        if record.code != provided_code:
            self._verifications.increment_attempts(record)
            if record.attempts_made >= record.attempt_limit:
                self._verifications.delete(record)
            raise VerificationError("验证码无效或已过期")
        return record

    def _issue_tokens(self, user: User) -> TokenPair:
        """Create access and refresh tokens for the provided user."""
        access_jti = security.generate_token_id()
        refresh_jti = security.generate_token_id()
        access_token = security.create_token(
            {"sub": str(user.id), "scope": "access", "jti": access_jti},
            timedelta(minutes=settings.access_token_expire_minutes),
        )
        refresh_token = security.create_token(
            {"sub": str(user.id), "scope": "refresh", "jti": refresh_jti},
            timedelta(minutes=settings.refresh_token_expire_minutes),
        )
        expires_at = datetime.utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes)
        self._refresh_tokens.create(user_id=user.id, token_id=refresh_jti, expires_at=expires_at)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def _validate_refresh_token(self, token: str):
        """Decode refresh token and ensure it is active."""
        payload = security.decode_token(token)
        if payload.get("scope") != "refresh":
            raise AuthenticationError("非法令牌")
        token_id = payload.get("jti")
        if not token_id:
            raise AuthenticationError("非法令牌")
        record = self._refresh_tokens.get(token_id)
        if record is None or record.revoked or record.expires_at <= datetime.utcnow():
            raise AuthenticationError("令牌已失效")
        user_id = int(payload["sub"])
        user = self._users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("用户不存在")
        return user, record

    def _limiter_keys(self, *, email: str, ip: str | None) -> list[str]:
        """Return rate limit keys for tracking attempts."""
        keys = [f"login:email:{email.lower()}"]
        if ip:
            keys.append(f"login:ip:{ip}")
        return keys

    @staticmethod
    def _generate_code(length: int = 6) -> str:
        """Generate a numeric one-time code."""
        digits = "0123456789"
        return "".join(secrets.choice(digits) for _ in range(length))

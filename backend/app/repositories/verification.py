"""Verification code persistence helpers."""

from datetime import datetime

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models import VerificationCode


class VerificationCodeRepository:
    """Manage verification codes for email confirmation or reset flows."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        email: str,
        code: str,
        purpose: str,
        expire_at: datetime,
        user_id: int | None = None,
        attempt_limit: int = 5,
    ) -> VerificationCode:
        """Persist a new verification code."""
        record = VerificationCode(
            email=email,
            code=code,
            purpose=purpose,
            expire_at=expire_at,
            user_id=user_id,
            attempt_limit=attempt_limit,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_valid(self, *, email: str, purpose: str, code: str) -> VerificationCode | None:
        """Return verification entry if it is valid."""
        statement = select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.code == code,
            VerificationCode.attempts_made < VerificationCode.attempt_limit,
            VerificationCode.expire_at > datetime.utcnow(),
        )
        return self._session.exec(statement).first()

    def get_latest(self, *, email: str, purpose: str) -> VerificationCode | None:
        """Return the latest non-expired verification entry for an email/purpose."""
        statement = (
            select(VerificationCode)
            .where(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.expire_at > datetime.utcnow(),
            )
            .order_by(desc(VerificationCode.created_at))
        )
        return self._session.exec(statement).first()

    def increment_attempts(self, record: VerificationCode) -> None:
        """Increment attempt counter."""
        record.attempts_made += 1
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

    def delete(self, record: VerificationCode) -> None:
        """Remove verification record after successful use."""
        self._session.delete(record)
        self._session.commit()

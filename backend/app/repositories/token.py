"""Refresh token repository."""

from datetime import datetime

from sqlmodel import Session, select

from app.models import RefreshToken


class RefreshTokenRepository:
    """Provide persistence helpers for refresh tokens."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, user_id: int, token_id: str, expires_at: datetime) -> RefreshToken:
        """Persist a refresh token."""
        token = RefreshToken(user_id=user_id, token_id=token_id, expires_at=expires_at)
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def revoke(self, token_id: str) -> None:
        """Mark token as revoked."""
        token = self.get(token_id)
        if token is None:
            return
        token.revoked = True
        self._session.add(token)
        self._session.commit()

    def get(self, token_id: str) -> RefreshToken | None:
        """Retrieve token by identifier."""
        statement = select(RefreshToken).where(RefreshToken.token_id == token_id)
        return self._session.exec(statement).first()

    def revoke_all_for_user(self, user_id: int) -> None:
        """Revoke all refresh tokens belonging to a user."""
        statement = select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        for token in self._session.exec(statement):
            token.revoked = True
            self._session.add(token)
        self._session.commit()

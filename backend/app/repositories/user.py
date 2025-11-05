"""Repository helpers for user persistence."""

from datetime import datetime

from sqlmodel import Session, select

from app.models import User


class UserRepository:
    """Encapsulate common persistence operations for users."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, email: str, password_hash: str) -> User:
        """Persist a new user instance."""
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        """Return the user with the provided email address."""
        statement = select(User).where(User.email == email)
        return self._session.exec(statement).first()

    def get_by_id(self, user_id: int) -> User | None:
        """Return user by identifier."""
        return self._session.get(User, user_id)

    def update_last_login(self, user: User) -> None:
        """Update the last login timestamp for the user."""
        user.last_login_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        self._session.add(user)
        self._session.commit()
    def exists(self, email: str) -> bool:
        """Return whether a user with the email exists."""
        return self.get_by_email(email) is not None

    def update_password(self, user: User, password_hash: str) -> None:
        """Update the stored password hash for a user."""
        user.password_hash = password_hash
        user.updated_at = datetime.utcnow()
        self._session.add(user)
        self._session.commit()

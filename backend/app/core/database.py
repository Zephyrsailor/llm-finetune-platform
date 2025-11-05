"""Database engine and session utilities."""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def get_session() -> Generator[Session, None, None]:
    """Provide a SQLModel session dependency."""
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Create tables if they do not exist (development helper)."""
    SQLModel.metadata.create_all(engine)

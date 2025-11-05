"""Audit log model capturing authentication events."""

from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """Audit trail for security sensitive events."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    event_type: str = Field(max_length=64, index=True)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

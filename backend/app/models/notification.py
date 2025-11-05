"""Notification center models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, Enum, JSON, Text
from sqlmodel import Field, SQLModel


class NotificationChannelType(StrEnum):
    """Supported outbound notification channel types."""

    WEBHOOK = "webhook"
    EMAIL = "email"
    IM = "im"


class NotificationDeliveryStatus(StrEnum):
    """Delivery state for notification records."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationChannel(SQLModel, table=True):
    """Workspace-scoped notification endpoint definition."""

    __tablename__ = "notification_channels"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    name: str = Field(max_length=100)
    channel_type: NotificationChannelType = Field(
        sa_column=Column(
            Enum(NotificationChannelType, name="notification_channel_type_enum"),
            nullable=False,
        ),
    )
    event_types: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    is_active: bool = Field(default=True)
    created_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class NotificationRecord(SQLModel, table=True):
    """Persisted notification send attempt."""

    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    channel_id: int = Field(foreign_key="notification_channels.id", index=True)
    event_type: str = Field(max_length=120, index=True)
    payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: NotificationDeliveryStatus = Field(
        default=NotificationDeliveryStatus.PENDING,
        sa_column=Column(
            Enum(NotificationDeliveryStatus, name="notification_delivery_status_enum"),
            nullable=False,
        ),
    )
    attempts: int = Field(default=0)
    next_retry_at: datetime | None = Field(default=None)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    dispatched_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


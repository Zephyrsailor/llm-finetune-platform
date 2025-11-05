"""Pydantic schemas for notification center APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import NotificationChannelType, NotificationDeliveryStatus


class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True, from_attributes=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    name: str
    channel_type: NotificationChannelType
    event_types: list[str]
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationChannelCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: int
    project_id: int | None = None
    name: str = Field(max_length=100)
    channel_type: NotificationChannelType
    event_types: list[str] = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class NotificationChannelUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=100)
    project_id: int | None = None
    event_types: list[str] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class NotificationEventResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True, from_attributes=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    channel_id: int
    event_type: str
    payload: dict[str, Any] | None = None
    status: NotificationDeliveryStatus
    attempts: int
    next_retry_at: datetime | None = None
    last_error: str | None = None
    dispatched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

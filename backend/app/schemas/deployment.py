"""Pydantic schemas for deployment API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import DeploymentStatus


class DeploymentCreateRequest(BaseModel):
    workspace_id: int
    project_id: int | None = None
    model_version_id: int
    environment: str = "production"
    replicas: int = Field(default=1, ge=1)
    max_batch_size: int = Field(default=16, ge=1)
    max_concurrency: int = Field(default=32, ge=1)
    notes: str | None = None


class DeploymentTrafficUpdateRequest(BaseModel):
    traffic_percent: float = Field(ge=0, le=100)


class DeploymentRollbackRequest(BaseModel):
    reason: str | None = None


class DeploymentEventResponse(BaseModel):
    id: int
    deployment_id: int
    event_type: str
    level: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class DeploymentInstanceResponse(BaseModel):
    id: int
    deployment_id: int
    environment: str
    status: DeploymentStatus
    endpoint_url: str | None = None
    access_token: str | None = None
    config: dict[str, Any]
    metrics: dict[str, Any]
    traffic_percent: float | None = None
    health_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    model_version_id: int
    environment: str
    status: DeploymentStatus
    endpoint_url: str | None = None
    access_token: str | None = None
    config: dict[str, Any]
    metrics: dict[str, Any]
    traffic_percent: Optional[float] = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    events: list[DeploymentEventResponse]
    instances: list[DeploymentInstanceResponse]


class DeploymentListResponse(BaseModel):
    deployments: list[DeploymentResponse]

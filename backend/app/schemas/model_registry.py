"""Pydantic schemas for model registry API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ModelVersionStatus


class ModelCreateRequest(BaseModel):
    workspace_id: int
    project_id: int | None = None
    name: str
    description: str | None = None
    base_model: str | None = None
    tags: list[str] = Field(default_factory=list)


class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    name: str
    description: str | None = None
    base_model: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime
    versions: list["ModelVersionResponse"] = Field(default_factory=list)


class ModelVersionCreateRequest(BaseModel):
    training_run_id: int | None = None
    evaluation_job_id: int | None = None
    metadata: dict[str, Any] | None = None
    notes: str | None = None
    deployment_target: str | None = None
    artifact_path: str | None = None


class ModelVersionStatusUpdateRequest(BaseModel):
    status: ModelVersionStatus
    notes: str | None = None
    deployment_target: str | None = None


class ModelVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    model_id: int
    version: int
    status: ModelVersionStatus
    artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    training_run_id: int | None = None
    evaluation_job_id: int | None = None
    evaluation_metrics: dict[str, Any] = Field(default_factory=dict)
    evaluation_report_path: str | None = None
    deployment_target: str | None = None
    notes: str | None = None
    created_by: int | None = None
    updated_by: int | None = None
    promoted_by: int | None = None
    promoted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ModelVersionExportResponse(BaseModel):
    path: str
    format: str

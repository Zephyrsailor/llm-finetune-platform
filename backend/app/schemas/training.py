"""Pydantic schemas for training templates and jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    TrainingAdapterType,
    TrainingJobStatus,
    EvaluationFeedbackKind,
    EvaluationFeedbackStatus,
)


class TrainingTemplateCreateRequest(BaseModel):
    workspace_id: int
    name: str
    base_model: str
    adapter_type: TrainingAdapterType = TrainingAdapterType.LORA
    description: str | None = None
    params: dict[str, Any] | None = None


class TrainingTemplateUpdateRequest(BaseModel):
    name: str | None = None
    base_model: str | None = None
    adapter_type: TrainingAdapterType | None = None
    description: str | None = None
    params: dict[str, Any] | None = None


class TrainingTemplateCloneRequest(BaseModel):
    name: str | None = None


class TrainingTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    base_model: str
    adapter_type: TrainingAdapterType
    params: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="params_json",
        serialization_alias="params",
    )
    is_builtin: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class TrainingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    job_id: int
    resumed_from_snapshot_id: int | None = None
    status: TrainingJobStatus
    started_at: datetime
    finished_at: datetime | None = None
    metrics: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metrics_json",
        serialization_alias="metrics",
    )
    artifact_uri: str | None = None
    exit_code: int | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metadata_json",
        serialization_alias="metadata",
    )


class TrainingJobCreateRequest(BaseModel):
    workspace_id: int
    dataset_version_id: int
    dataset_format_version_id: int | None = None
    training_template_id: int | None = None
    project_id: int | None = None
    base_model: str | None = None
    adapter_type: TrainingAdapterType | None = None
    params: dict[str, Any] | None = None
    notes: str | None = None
    requested_gpus: int | None = None
    queue_name: str | None = None


class TrainingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    dataset_version_id: int
    dataset_format_version_id: int | None = None
    training_template_id: int | None = None
    base_model: str
    adapter_type: TrainingAdapterType
    status: TrainingJobStatus
    params: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="params_json",
        serialization_alias="params",
    )
    notes: str | None = None
    scheduled_by: int
    scheduled_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    requested_gpus: int
    queue_name: str
    latest_run: TrainingRunResponse | None = None


class TrainingWizardDraftRequest(BaseModel):
    workspace_id: int
    payload: dict[str, Any] | None = None


class TrainingWizardDraftResponse(BaseModel):
    workspace_id: int
    payload: dict[str, Any] | None = None
    updated_at: datetime | None = None


class TrainingWizardValidateRequest(BaseModel):
    workspace_id: int
    project_id: int | None = None
    dataset_version_id: int
    dataset_format_version_id: int | None = None
    training_template_id: int | None = None
    base_model: str | None = None
    adapter_type: TrainingAdapterType | None = None
    params: dict[str, Any] | None = None
    requested_gpus: int | None = None
    queue_name: str | None = None


class TrainingWizardValidateResponse(BaseModel):
    workspace_id: int
    project_id: int | None = None
    dataset_version_id: int
    dataset_format_version_id: int | None = None
    training_template_id: int | None = None
    base_model: str
    adapter_type: TrainingAdapterType
    params: dict[str, Any]
    requested_gpus: int
    queue_name: str


class TrainingFeedbackSummaryItem(BaseModel):
    id: int
    evaluation_job_id: int
    training_run_id: int | None = None
    kind: EvaluationFeedbackKind
    status: EvaluationFeedbackStatus
    body: str
    tags: list[str] = Field(default_factory=list)
    metric_name: str | None = None
    metric_value: float | None = None
    created_by: int
    created_at: datetime


class TrainingFeedbackSummaryResponse(BaseModel):
    workspace_id: int
    project_id: int | None = None
    items: list[TrainingFeedbackSummaryItem]

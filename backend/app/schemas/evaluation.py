"""Pydantic schemas for evaluation templates and jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    EvaluationTaskType,
    EvaluationJobStatus,
    EvaluationTriggerMode,
    EvaluationFeedbackKind,
    EvaluationFeedbackStatus,
)


class EvaluationTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    key: str
    name: str
    description: str | None = None
    task_type: EvaluationTaskType
    metrics: list[str] = Field(default_factory=list)
    config: dict[str, Any] | None = Field(
        default=None,
        alias="config_json",
        validation_alias="config_json",
        serialization_alias="config",
    )
    is_builtin: bool
    workspace_id: int | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    training_run_id: int | None = None
    evaluation_template_id: int
    dataset_version_id: int | None = None
    dataset_path: str | None = None
    artifact_path: str | None = None
    report_path: str | None = None
    status: EvaluationJobStatus
    metrics: dict[str, Any] | None = Field(
        default=None,
        alias="metrics_json",
        validation_alias="metrics_json",
        serialization_alias="metrics",
    )
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trigger_mode: EvaluationTriggerMode


class EvaluationReportCase(BaseModel):
    reference: str
    prediction: str
    score: float | None = None


class EvaluationReportResponse(BaseModel):
    job: Dict[str, Any]
    metrics: Dict[str, Any]
    cases: Dict[str, List[EvaluationReportCase]]
    artifacts: Dict[str, str]
    training: Dict[str, Any]
    dataset: Dict[str, Any] | None = None
    report_markdown: str | None = None
    report_html: str | None = None


class EvaluationReportShareResponse(BaseModel):
    token: str
    share_path: str
    expires_at: datetime


class EvaluationFeedbackCreateRequest(BaseModel):
    workspace_id: int
    kind: EvaluationFeedbackKind = EvaluationFeedbackKind.COMMENT
    body: str
    tags: list[str] = Field(default_factory=list)
    status: EvaluationFeedbackStatus | None = None
    training_run_id: int | None = None
    metric_name: str | None = None
    metric_value: float | None = None


class EvaluationFeedbackUpdateRequest(BaseModel):
    body: str | None = None
    status: EvaluationFeedbackStatus | None = None
    tags: list[str] | None = None
    metric_name: str | None = None
    metric_value: float | None = None


class EvaluationFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    evaluation_job_id: int
    training_run_id: int | None = None
    kind: EvaluationFeedbackKind
    status: EvaluationFeedbackStatus
    body: str
    tags: list[str] = Field(default_factory=list)
    metric_name: str | None = None
    metric_value: float | None = None
    created_by: int
    updated_by: int | None = None
    resolved_by: int | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class EvaluationFeedbackExportResponse(BaseModel):
    path: str
    format: str
    count: int

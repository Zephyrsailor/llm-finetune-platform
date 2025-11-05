"""Pydantic schemas for training monitoring APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from app.models import (
    TrainingAlertOperator,
    TrainingAlertStatus,
    TrainingJobStatus,
    TrainingMetricName,
)


class TrainingMetricSampleResponse(BaseModel):
    run_id: int
    metric: TrainingMetricName
    value: float
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TrainingAlertResponse(BaseModel):
    id: int
    rule_id: int
    run_id: int
    value: float
    status: TrainingAlertStatus
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class TrainingAlertRuleResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    metric: TrainingMetricName
    operator: TrainingAlertOperator
    threshold: float
    cooldown_seconds: int
    is_active: bool
    channels: dict[str, Any] | None = Field(default=None, validation_alias="channels_json", serialization_alias="channels")
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TrainingAlertRuleCreateRequest(BaseModel):
    workspace_id: int
    name: str
    metric: TrainingMetricName
    operator: TrainingAlertOperator
    threshold: float
    cooldown_seconds: int = 300
    channels: dict[str, Any] | None = None


class TrainingAlertRuleUpdateRequest(BaseModel):
    name: str | None = None
    operator: TrainingAlertOperator | None = None
    threshold: float | None = None
    cooldown_seconds: int | None = None
    is_active: bool | None = None
    channels: dict[str, Any] | None = None


class TrainingAlertStatusUpdateRequest(BaseModel):
    status: TrainingAlertStatus
    notes: str | None = None


class TrainingMonitorRunResponse(BaseModel):
    run_id: int
    job_id: int
    workspace_id: int
    project_id: int | None = None
    status: TrainingJobStatus
    started_at: datetime
    finished_at: datetime | None = None
    job_error_message: str | None = None
    latest_metrics: list[TrainingMetricSampleResponse]
    alerts: list[TrainingAlertResponse]
    latest_evaluation: dict[str, Any] | None = None
    model_config = ConfigDict(from_attributes=True)


class TrainingAlertsExportResponse(BaseModel):
    workspace_id: int
    generated_at: datetime
    count: int


class TrainingMetricsExportResponse(BaseModel):
    run_id: int
    generated_at: datetime
    count: int

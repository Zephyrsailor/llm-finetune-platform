"""Pydantic schemas for dataset APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import (
    DataCleaningJobStatus,
    DatasetFormatStatus,
    DatasetFormatType,
    DatasetSourceType,
    DatasetStatus,
    DatasetVersionStatus,
    QualityEvaluationStatus,
)


class DatasetResponse(BaseModel):
    """Dataset response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    source_type: DatasetSourceType
    source_uri: str | None = None
    storage_path: str | None = None
    data_type: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    tags: list[str]
    notes: str | None = None
    status: DatasetStatus
    reference_dataset_id: int | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class DataCleaningJobResponse(BaseModel):
    """Data cleaning job descriptor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_version_id: int
    status: DataCleaningJobStatus
    template_id: int | None = None
    template_snapshot: dict | None = None
    logs_path: str | None = None
    error_message: str | None = None
    summary_path: str | None = None
    export_manifest: dict | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CleaningTemplateResponse(BaseModel):
    """Cleaning template payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    is_active: bool
    version: int
    steps: list[dict]
    created_at: datetime
    updated_at: datetime


class CleaningAssignmentResponse(BaseModel):
    """Dataset to template assignment."""

    model_config = ConfigDict(from_attributes=True)

    dataset_id: int
    template_id: int
    enabled: bool
    assigned_at: datetime


class CleaningSummaryResponse(BaseModel):
    """Stats and artefacts for a cleaning job."""

    dataset_id: int
    dataset_version_id: int
    status: DataCleaningJobStatus | None = None
    stats: dict[str, Any]
    template: dict | None = None
    logs_path: str | None = None
    summary_path: str | None = None
    export_manifest: dict | None = None


class QualityEvaluationJobResponse(BaseModel):
    """Quality evaluation job descriptor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_version_id: int
    status: QualityEvaluationStatus
    logs_path: str | None = None
    error_message: str | None = None
    summary_path: str | None = None
    export_manifest: dict | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class QualitySummaryResponse(BaseModel):
    """Quality evaluation summary payload."""

    dataset_id: int
    dataset_version_id: int
    status: QualityEvaluationStatus | None = None
    stats: dict[str, Any]
    summary_path: str | None = None
    report_manifest: dict | None = None
    logs_path: str | None = None


class DatasetVersionResponse(BaseModel):
    """Dataset version payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    version: int
    status: DatasetVersionStatus
    location_uri: str | None = None
    stats_json: dict[str, Any] | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class DatasetVersionCreateResponse(BaseModel):
    """Combined response for version creation."""

    version: DatasetVersionResponse
    job: DataCleaningJobResponse
    quality_job: QualityEvaluationJobResponse | None = None


class DatasetFormatVersionResponse(BaseModel):
    """Standardised dataset artefact response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_version_id: int
    format: DatasetFormatType
    status: DatasetFormatStatus
    path: str | None = None
    logs_path: str | None = None
    checksum_sha256: str | None = None
    file_size_bytes: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None

"""Pydantic schemas for training snapshot operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import TrainingSnapshotTriggerType


class TrainingSnapshotResponse(BaseModel):
    """Snapshot metadata returned to the client."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    workspace_id: int
    job_id: int
    run_id: int
    path: str
    step: int | None = None
    epoch: int | None = None
    metrics: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metrics_json",
        serialization_alias="metrics",
    )
    trigger_type: TrainingSnapshotTriggerType
    created_by: int | None = None
    created_at: datetime
    notes: str | None = None
    restored_at: datetime | None = None
    restored_by: int | None = None


class TrainingSnapshotResumeRequest(BaseModel):
    """Optional note passed when resuming from a snapshot."""

    notes: str | None = None


class TrainingSnapshotRollbackRequest(BaseModel):
    """Optional reason recorded when rolling back to a snapshot."""

    reason: str | None = None

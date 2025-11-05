"""Dashboard response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


StageStatusValue = Literal["not_started", "in_progress", "completed", "unknown"]


class StageStatus(BaseModel):
    """Status information for a single delivery stage."""

    stage: str = Field(description="Identifier of the stage, e.g. data_ingestion")
    status: StageStatusValue = Field(description="Current status value")
    responsible: Optional[str] = Field(default=None, description="Responsible member email or name")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of the latest update if available")
    notes: Optional[str] = Field(default=None, description="Supplemental context for the status")


class MetricPlaceholder(BaseModel):
    """Placeholder KPI entry for future metric integration."""

    key: str
    label: str
    description: str
    value: Optional[float] = None
    unit: Optional[str] = None


class WorkspaceSummary(BaseModel):
    """Aggregated dashboard information for a single workspace."""

    workspace_id: int
    workspace_name: str
    stages: list[StageStatus]
    metrics: list[MetricPlaceholder]


class DashboardSummary(BaseModel):
    """Top-level dashboard summary response."""

    generated_at: datetime
    workspaces: list[WorkspaceSummary]

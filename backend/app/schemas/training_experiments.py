"""Pydantic schemas for training experiment metadata APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrainingExperimentSummary(BaseModel):
    run_id: int
    job_id: int
    workspace_id: int
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    base_model: str
    adapter_type: str
    dataset: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)


class TrainingExperimentDetail(TrainingExperimentSummary):
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: str | None = None
    exit_code: int | None = None


class TrainingExperimentCompareRequest(BaseModel):
    run_a_id: int = Field(gt=0)
    run_b_id: int = Field(gt=0)


class TrainingExperimentCompareResponse(BaseModel):
    run_a: TrainingExperimentSummary
    run_b: TrainingExperimentSummary
    diff: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    snapshots: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    alerts: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class TrainingExperimentExportRequest(BaseModel):
    workspace_id: int
    run_ids: list[int] = Field(min_length=1)
    format: str = Field(default="json")


class TrainingExperimentExportResponse(BaseModel):
    workspace_id: int
    format: str
    path: str
    generated_at: str | None = None
    size_bytes: int

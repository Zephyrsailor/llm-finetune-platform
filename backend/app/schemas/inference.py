"""Pydantic schemas for inference API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class InferenceInvokeRequest(BaseModel):
    workspace_id: int
    deployment_id: int | None = None
    model_version_id: int | None = None
    inputs: list[str] = Field(min_length=1)
    parameters: Optional[dict[str, Any]] = None


class GeneratedOutput(BaseModel):
    output: str


class InferenceInvokeResponse(BaseModel):
    call_id: int
    deployment_id: int
    model_version_id: int
    outputs: list[GeneratedOutput]
    latency_ms: float
    input_tokens: int
    output_tokens: int


class InferenceLogResponse(BaseModel):
    id: int
    deployment_id: int | None = None
    model_version_id: int | None = None
    status: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: datetime


class InferenceApiKeyCreateRequest(BaseModel):
    workspace_id: int
    name: str = Field(max_length=128)
    rate_limit_per_minute: int | None = Field(default=None, ge=1)
    daily_quota: int | None = Field(default=None, ge=1)


class InferenceApiKeyResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    rate_limit_per_minute: int | None = None
    daily_quota: int | None = None
    created_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class InferenceApiKeyCreationResponse(BaseModel):
    api_key: InferenceApiKeyResponse
    secret: str


class InferenceLogListResponse(BaseModel):
    logs: list[InferenceLogResponse]


class InferenceApiKeyListResponse(BaseModel):
    items: list[InferenceApiKeyResponse]

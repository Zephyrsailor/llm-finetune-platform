"""Pydantic schemas for runtime monitoring API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import RuntimeAlertOperator, RuntimeAlertStatus, RuntimeMetricName


class RuntimeDailyUsage(BaseModel):
    requests: int = 0
    tokens: int = 0


class RuntimeMetricSummary(BaseModel):
    deployment_id: int | None = None
    total_calls: int
    success_count: int
    rate_limited_count: int
    error_count: int
    latency_p95_ms: float | None = None
    qps: float
    error_rate: float
    token_throughput_per_minute: float
    token_throughput_per_second: float
    daily_usage: RuntimeDailyUsage | None = None
    metrics: dict[str, Any] | None = None
    environment: str | None = None
    status: str | None = None
    traffic_percent: float | None = None


class RuntimeResourceUsageResponse(BaseModel):
    deployment_id: int | None
    environment: str | None
    status: str
    traffic_percent: float | None = None
    metrics: dict[str, Any]
    updated_at: datetime
    qps: float | None = None
    error_rate: float | None = None
    latency_p95_ms: float | None = None
    token_throughput_per_minute: float | None = None


class RuntimeAlertRuleCreateRequest(BaseModel):
    workspace_id: int
    deployment_id: int | None = Field(default=None)
    name: str = Field(max_length=200)
    metric: RuntimeMetricName
    operator: RuntimeAlertOperator
    threshold: float
    cooldown_seconds: int = Field(ge=0)
    channels: dict[str, Any] | None = None


class RuntimeAlertRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    operator: RuntimeAlertOperator | None = None
    threshold: float | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    channels: dict[str, Any] | None = None
    deployment_id: int | None = None


class RuntimeAlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    deployment_id: int | None
    name: str
    metric: RuntimeMetricName
    operator: RuntimeAlertOperator
    threshold: float
    cooldown_seconds: int
    is_active: bool
    channels: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RuntimeAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    deployment_id: int | None
    rule_id: int
    value: float
    status: RuntimeAlertStatus
    triggered_at: datetime
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    notes: str | None = None
    recommendation: str | None = None
    created_at: datetime
    updated_at: datetime


class RuntimeAlertStatusUpdateRequest(BaseModel):
    status: RuntimeAlertStatus
    notes: str | None = Field(default=None, max_length=1000)


class RuntimeOverviewResponse(BaseModel):
    window_minutes: int
    metrics: RuntimeMetricSummary
    per_deployment: list[RuntimeMetricSummary]
    alerts: list[RuntimeAlertResponse]
    resource_usage: list[RuntimeResourceUsageResponse]

"""Runtime monitoring SQLModel definitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Column, Enum, Float, JSON
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.deployment import Deployment
from app.models.user import User
from app.models.workspace import Workspace


class RuntimeMetricName(StrEnum):
    """Supported runtime metric identifiers for alert evaluation."""

    QPS = "qps"
    LATENCY_P95_MS = "latency_p95_ms"
    ERROR_RATE = "error_rate"
    TOKEN_THROUGHPUT_PER_MINUTE = "token_throughput_per_minute"
    GPU_MEMORY_MB = "gpu_memory_mb"
    GPU_UTILIZATION = "gpu_utilization"


class RuntimeAlertOperator(StrEnum):
    """Comparison operators for runtime alert thresholds."""

    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"


class RuntimeAlertStatus(StrEnum):
    """Lifecycle status for runtime alerts."""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RuntimeAlertRule(SQLModel, table=True):
    """Threshold rule definition for runtime monitoring."""

    __tablename__ = "runtime_alert_rules"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    deployment_id: int | None = Field(default=None, foreign_key="deployments.id", index=True)
    name: str = Field(max_length=200)
    metric: RuntimeMetricName = Field(
        sa_column=Column(Enum(RuntimeMetricName, name="runtime_metric_name"))
    )
    operator: RuntimeAlertOperator = Field(
        sa_column=Column(Enum(RuntimeAlertOperator, name="runtime_alert_operator"))
    )
    threshold: float = Field(sa_column=Column(Float))
    cooldown_seconds: int = Field(default=300)
    is_active: bool = Field(default=True)
    channels_json: dict | None = Field(sa_column=Column(JSON, default=None))
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    deployment: Optional[Deployment] = Relationship(sa_relationship=relationship("Deployment"))
    creator: Optional[User] = Relationship(sa_relationship=relationship("User"))
    alerts: list["RuntimeAlert"] = Relationship(
        back_populates="rule",
        sa_relationship=relationship(
            "RuntimeAlert",
            back_populates="rule",
            cascade="all, delete-orphan",
        ),
    )


class RuntimeAlert(SQLModel, table=True):
    """Alert instance triggered by runtime threshold violation."""

    __tablename__ = "runtime_alerts"

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="runtime_alert_rules.id", index=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    deployment_id: int | None = Field(default=None, foreign_key="deployments.id", index=True)
    value: float = Field(sa_column=Column(Float))
    status: RuntimeAlertStatus = Field(
        default=RuntimeAlertStatus.TRIGGERED,
        sa_column=Column(Enum(RuntimeAlertStatus, name="runtime_alert_status")),
    )
    triggered_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    acknowledged_by: int | None = Field(default=None, foreign_key="users.id")
    acknowledged_at: datetime | None = Field(default=None)
    resolved_by: int | None = Field(default=None, foreign_key="users.id")
    resolved_at: datetime | None = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=1000)
    recommendation: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    rule: RuntimeAlertRule = Relationship(
        back_populates="alerts",
        sa_relationship=relationship("RuntimeAlertRule", back_populates="alerts"),
    )
    deployment: Optional[Deployment] = Relationship(sa_relationship=relationship("Deployment"))

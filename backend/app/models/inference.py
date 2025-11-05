"""Inference domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, Enum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlmodel import Field, SQLModel, Relationship

from app.models.workspace import Workspace, Project
from app.models.deployment import Deployment
from app.models.model_registry import ModelVersion
from app.models.user import User


class InferenceCallStatus(StrEnum):
    """Status of an inference invocation."""

    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class InferenceCall(SQLModel, table=True):
    """Audit log for inference invocations."""

    __tablename__ = "inference_calls"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    deployment_id: int | None = Field(default=None, foreign_key="deployments.id", index=True)
    model_version_id: int | None = Field(default=None, foreign_key="model_versions.id", index=True)
    api_key_id: int | None = Field(default=None, foreign_key="inference_api_keys.id")
    user_id: int | None = Field(default=None, foreign_key="users.id")
    request_payload: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    response_payload: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    status: InferenceCallStatus = Field(
        default=InferenceCallStatus.SUCCESS,
        sa_column=Column(Enum(InferenceCallStatus, name="inference_call_status"), nullable=False),
    )
    latency_ms: float | None = Field(default=None)
    input_tokens: int | None = Field(default=None)
    output_tokens: int | None = Field(default=None)
    error_message: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Project | None = Relationship(sa_relationship=relationship("Project"))
    deployment: Deployment | None = Relationship(sa_relationship=relationship("Deployment"))
    model_version: ModelVersion | None = Relationship(sa_relationship=relationship("ModelVersion"))
    api_key: "InferenceApiKey | None" = Relationship(
        sa_relationship=relationship("InferenceApiKey", back_populates="calls")
    )
    user: User | None = Relationship(sa_relationship=relationship("User"))


class UsageWindowScope(StrEnum):
    """Supported aggregation windows for quota tracking."""

    MINUTE = "minute"
    DAY = "day"


class InferenceUsage(SQLModel, table=True):
    """Aggregated usage counters for rate limiting and quotas."""

    __tablename__ = "inference_usage"
    __table_args__ = (
        UniqueConstraint("workspace_id", "scope", "window_start", name="uq_inference_usage_window"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    scope: UsageWindowScope = Field(
        default=UsageWindowScope.MINUTE,
        sa_column=Column(Enum(UsageWindowScope, name="usage_window_scope"), nullable=False),
    )
    window_start: datetime = Field(nullable=False, index=True)
    request_count: int = Field(default=0, nullable=False)
    token_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class InferenceApiKey(SQLModel, table=True):
    """API key allowing programmatic inference access."""

    __tablename__ = "inference_api_keys"
    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_inference_api_keys_prefix"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    name: str = Field(max_length=128)
    key_prefix: str = Field(max_length=16, index=True)
    key_hash: str = Field(max_length=512)
    rate_limit_per_minute: int | None = Field(default=None)
    daily_quota: int | None = Field(default=None)
    is_active: bool = Field(default=True)
    created_by: int | None = Field(default=None, foreign_key="users.id")
    revoked_at: datetime | None = Field(default=None)
    last_used_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    creator: User | None = Relationship(sa_relationship=relationship("User"))
    calls: list[InferenceCall] = Relationship(
        sa_relationship=relationship("InferenceCall", back_populates="api_key")
    )

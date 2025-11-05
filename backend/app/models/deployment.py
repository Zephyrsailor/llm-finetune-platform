"""Deployment domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Column, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.model_registry import ModelVersion
from app.models.workspace import Workspace, Project


class DeploymentStatus(StrEnum):
    """Lifecycle status for deployed model instances."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Deployment(SQLModel, table=True):
    """Deployment instance metadata."""

    __tablename__ = "deployments"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    model_version_id: int = Field(foreign_key="model_versions.id", index=True)
    environment: str = Field(max_length=128, default="production")
    status: DeploymentStatus = Field(
        default=DeploymentStatus.PENDING,
        sa_column=Column(Enum(DeploymentStatus, name="deployment_status"), nullable=False),
    )
    endpoint_url: str | None = Field(default=None, max_length=512)
    access_token: str | None = Field(default=None, max_length=512)
    config_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    metrics_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    traffic_percent: float | None = Field(default=None)
    notes: str | None = Field(default=None, max_length=2000)
    created_by: int | None = Field(default=None, foreign_key="users.id")
    updated_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))
    model_version: ModelVersion = Relationship(sa_relationship=relationship("ModelVersion"))
    instances: list["DeploymentInstance"] = Relationship(
        sa_relationship=relationship(
            "DeploymentInstance",
            back_populates="deployment",
            cascade="all, delete-orphan",
        )
    )
    events: list["DeploymentEvent"] = Relationship(
        sa_relationship=relationship("DeploymentEvent", back_populates="deployment", cascade="all, delete-orphan")
    )


class DeploymentInstance(SQLModel, table=True):
    """Concrete runtime instance spawned by a deployment."""

    __tablename__ = "deployment_instances"

    id: int | None = Field(default=None, primary_key=True)
    deployment_id: int = Field(foreign_key="deployments.id", index=True)
    environment: str = Field(max_length=128)
    status: DeploymentStatus = Field(
        default=DeploymentStatus.PENDING,
        sa_column=Column(Enum(DeploymentStatus, name="deployment_status"), nullable=False),
    )
    endpoint_url: str | None = Field(default=None, max_length=512)
    access_token: str | None = Field(default=None, max_length=512)
    config_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    metrics_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    traffic_percent: float | None = Field(default=None)
    health_checked_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    deployment: Deployment = Relationship(
        sa_relationship=relationship("Deployment", back_populates="instances")
    )


class DeploymentEvent(SQLModel, table=True):
    """Deployment event log."""

    __tablename__ = "deployment_events"

    id: int | None = Field(default=None, primary_key=True)
    deployment_id: int = Field(foreign_key="deployments.id", index=True)
    event_type: str = Field(max_length=128)
    level: str = Field(max_length=32)
    message: str = Field(max_length=1024)
    payload_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    deployment: Deployment = Relationship(sa_relationship=relationship("Deployment", back_populates="events"))

"""Model registry domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Column, Enum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.workspace import Workspace, Project
from app.models.training import TrainingRun
from app.models.evaluation import EvaluationJob


class ModelVersionStatus(StrEnum):
    """Lifecycle status for a registered model version."""

    CANDIDATE = "candidate"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


class RegisteredModel(SQLModel, table=True):
    """Top-level registered model entity."""

    __tablename__ = "registered_models"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_registered_model_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    name: str = Field(max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=1024)
    base_model: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    created_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))
    versions: list["ModelVersion"] = Relationship(sa_relationship=relationship(
        "ModelVersion",
        back_populates="model",
        cascade="all, delete-orphan",
        order_by="ModelVersion.created_at.desc()",
    ))


class ModelVersion(SQLModel, table=True):
    """Registered model version metadata."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_version_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="registered_models.id", index=True, nullable=False)
    version: int = Field(nullable=False)
    status: ModelVersionStatus = Field(
        default=ModelVersionStatus.CANDIDATE,
        sa_column=Column(
            Enum(ModelVersionStatus, name="model_version_status"),
            nullable=False,
            default=ModelVersionStatus.CANDIDATE,
        ),
    )
    artifact_path: str | None = Field(default=None, max_length=1024)
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    training_run_id: int | None = Field(default=None, foreign_key="training_runs.id", index=True)
    evaluation_job_id: int | None = Field(default=None, foreign_key="evaluation_jobs.id", index=True)
    evaluation_metrics_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    evaluation_report_path: str | None = Field(default=None, max_length=1024)
    deployment_target: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    created_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    promoted_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    promoted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    model: RegisteredModel = Relationship(sa_relationship=relationship("RegisteredModel", back_populates="versions"))
    training_run: Optional[TrainingRun] = Relationship(sa_relationship=relationship("TrainingRun"))
    evaluation_job: Optional[EvaluationJob] = Relationship(sa_relationship=relationship("EvaluationJob"))

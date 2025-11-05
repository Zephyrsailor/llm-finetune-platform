"""Evaluation template and job models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.workspace import Workspace, Project
from app.models.user import User
from app.models.dataset import DatasetVersion

if TYPE_CHECKING:  # pragma: no cover
    from app.models.training import TrainingRun


class EvaluationTaskType(StrEnum):
    """Supported evaluation task types."""

    QA = "question_answering"
    CONVERSATION = "conversation"
    CLASSIFICATION = "classification"


class EvaluationJobStatus(StrEnum):
    """Lifecycle status for evaluation jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationTemplate(SQLModel, table=True):
    """Standardized evaluation template definition."""

    __tablename__ = "evaluation_templates"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(max_length=100, unique=True, index=True)
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    task_type: EvaluationTaskType = Field(
        sa_column=Column(Enum(EvaluationTaskType, name="evaluation_task_type"))
    )
    metrics: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    config_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    is_builtin: bool = Field(default=False, index=True)
    workspace_id: int | None = Field(default=None, foreign_key="workspaces.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Optional[Workspace] = Relationship(sa_relationship=relationship("Workspace"))


class EvaluationTriggerMode(StrEnum):
    """Trigger mode for evaluation jobs."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"


class EvaluationJob(SQLModel, table=True):
    """Evaluation job triggered for a training run or baseline model."""

    __tablename__ = "evaluation_jobs"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id", index=True)
    training_run_id: Optional[int] = Field(default=None, foreign_key="training_runs.id", index=True)
    evaluation_template_id: int = Field(foreign_key="evaluation_templates.id", index=True)
    dataset_version_id: Optional[int] = Field(
        default=None,
        foreign_key="dataset_versions.id",
        index=True,
    )
    dataset_path: Optional[str] = Field(default=None, max_length=1024)
    artifact_path: Optional[str] = Field(default=None, max_length=1024)
    report_path: Optional[str] = Field(default=None, max_length=1024)
    status: EvaluationJobStatus = Field(
        sa_column=Column(Enum(EvaluationJobStatus, name="evaluation_job_status")),
        default=EvaluationJobStatus.PENDING,
    )
    metrics_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, default=None))
    error_message: Optional[str] = Field(default=None, max_length=1000)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    trigger_mode: EvaluationTriggerMode = Field(
        default=EvaluationTriggerMode.MANUAL,
        sa_column=Column(
            Enum(EvaluationTriggerMode, name="evaluation_trigger_mode"),
            default=EvaluationTriggerMode.MANUAL,
        ),
    )

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))
    training_run: Optional[TrainingRun] = Relationship(
        sa_relationship=relationship("TrainingRun", back_populates="evaluations")
    )
    template: EvaluationTemplate = Relationship(sa_relationship=relationship("EvaluationTemplate"))
    dataset_version: Optional[DatasetVersion] = Relationship(
        sa_relationship=relationship("DatasetVersion")
    )
    creator: Optional[User] = Relationship(sa_relationship=relationship("User"))
    feedback_entries: list["EvaluationFeedback"] = Relationship(
        sa_relationship=relationship(
            "EvaluationFeedback",
            back_populates="evaluation_job",
            cascade="all, delete-orphan",
        )
    )


class EvaluationFeedbackKind(StrEnum):
    """Types of feedback that can be attached to an evaluation report."""

    COMMENT = "comment"
    TODO = "todo"
    BUSINESS_METRIC = "business_metric"


class EvaluationFeedbackStatus(StrEnum):
    """Lifecycle status for feedback items."""

    OPEN = "open"
    RESOLVED = "resolved"


class EvaluationFeedback(SQLModel, table=True):
    """Feedback, TODOs, and business metrics linked to evaluation jobs."""

    __tablename__ = "evaluation_feedback"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    evaluation_job_id: int = Field(foreign_key="evaluation_jobs.id", index=True)
    training_run_id: int | None = Field(default=None, foreign_key="training_runs.id", index=True)
    kind: EvaluationFeedbackKind = Field(
        default=EvaluationFeedbackKind.COMMENT,
        sa_column=Column(
            Enum(EvaluationFeedbackKind, name="evaluation_feedback_kind"),
            nullable=False,
            default=EvaluationFeedbackKind.COMMENT,
        ),
    )
    status: EvaluationFeedbackStatus = Field(
        default=EvaluationFeedbackStatus.OPEN,
        sa_column=Column(
            Enum(EvaluationFeedbackStatus, name="evaluation_feedback_status"),
            nullable=False,
            default=EvaluationFeedbackStatus.OPEN,
        ),
    )
    body: str = Field(max_length=4096)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    metric_name: str | None = Field(default=None, max_length=200)
    metric_value: float | None = Field(default=None)
    created_by: int = Field(foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    resolved_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    resolved_at: datetime | None = Field(default=None)

    evaluation_job: EvaluationJob = Relationship(back_populates="feedback_entries")
    training_run: Optional["TrainingRun"] = Relationship(sa_relationship=relationship("TrainingRun"))
    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))

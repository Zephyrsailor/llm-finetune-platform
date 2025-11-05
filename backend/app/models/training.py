"""Training related SQLModel definitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Column, Enum, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.dataset import DatasetVersion, DatasetFormatVersion
from app.models.workspace import Workspace, Project
from app.models.user import User
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.models.evaluation import EvaluationJob


class TrainingAdapterType(StrEnum):
    """Supported parameter-efficient training adapter strategies."""

    LORA = "lora"
    QLORA = "qlora"
    DORA = "dora"
    FULL_FINE_TUNE = "full-finetune"


class TrainingJobStatus(StrEnum):
    """Lifecycle status for training jobs."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TrainingTemplate(SQLModel, table=True):
    """Reusable training template definitions scoped to workspace."""

    __tablename__ = "training_templates"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    base_model: str = Field(max_length=300)
    adapter_type: TrainingAdapterType = Field(
        sa_column=Column(Enum(TrainingAdapterType, name="training_adapter_type")),
        default=TrainingAdapterType.LORA,
    )
    params_json: dict = Field(sa_column=Column(JSON, default=dict))
    is_builtin: bool = Field(default=False)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    creator: Optional[User] = Relationship(sa_relationship=relationship("User"))
    jobs: list["TrainingJob"] = Relationship(
        back_populates="template",
        sa_relationship=relationship(
            "TrainingJob",
            back_populates="template",
        ),
    )


class TrainingJob(SQLModel, table=True):
    """Training job requested via TrainingService."""

    __tablename__ = "training_jobs"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id", index=True)
    dataset_version_id: int = Field(foreign_key="dataset_versions.id", index=True)
    dataset_format_version_id: Optional[int] = Field(
        default=None,
        foreign_key="dataset_format_versions.id",
        index=True,
    )
    training_template_id: Optional[int] = Field(
        default=None,
        foreign_key="training_templates.id",
        index=True,
    )
    base_model: str = Field(max_length=300)
    adapter_type: TrainingAdapterType = Field(
        sa_column=Column(Enum(TrainingAdapterType, name="training_job_adapter_type")),
        default=TrainingAdapterType.LORA,
    )
    status: TrainingJobStatus = Field(
        sa_column=Column(Enum(TrainingJobStatus, name="training_job_status")),
        default=TrainingJobStatus.PENDING,
    )
    params_json: dict = Field(sa_column=Column(JSON, default=dict))
    notes: Optional[str] = Field(default=None, max_length=1000)
    scheduled_by: int = Field(foreign_key="users.id", index=True)
    scheduled_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    requested_gpus: int = Field(default=1, ge=1)
    queue_name: str = Field(default="default", max_length=100)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))
    dataset_version: DatasetVersion = Relationship(sa_relationship=relationship("DatasetVersion"))
    dataset_format_version: Optional[DatasetFormatVersion] = Relationship(
        sa_relationship=relationship("DatasetFormatVersion")
    )
    template: Optional[TrainingTemplate] = Relationship(
        back_populates="jobs",
        sa_relationship=relationship(
            "TrainingTemplate",
            back_populates="jobs",
        ),
    )
    creator: User = Relationship(sa_relationship=relationship("User"))
    runs: list["TrainingRun"] = Relationship(
        back_populates="job",
        sa_relationship=relationship(
            "TrainingRun",
            back_populates="job",
            cascade="all, delete-orphan",
        ),
    )


class TrainingRun(SQLModel, table=True):
    """Execution attempt for a training job."""

    __tablename__ = "training_runs"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="training_jobs.id", index=True)
    status: TrainingJobStatus = Field(
        sa_column=Column(Enum(TrainingJobStatus, name="training_run_status")),
        default=TrainingJobStatus.RUNNING,
    )
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    finished_at: Optional[datetime] = Field(default=None)
    metrics_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, default=None))
    artifact_uri: Optional[str] = Field(default=None, max_length=512)
    exit_code: Optional[int] = Field(default=None)
    resumed_from_snapshot_id: Optional[int] = Field(
        default=None, foreign_key="training_snapshots.id", index=True
    )
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON, default=None))

    job: TrainingJob = Relationship(
        back_populates="runs",
        sa_relationship=relationship("TrainingJob", back_populates="runs"),
    )
    events: list["TrainingEvent"] = Relationship(
        back_populates="run",
        sa_relationship=relationship(
            "TrainingEvent",
            back_populates="run",
            cascade="all, delete-orphan",
        ),
    )
    metric_samples: list["TrainingMetricSample"] = Relationship(
        back_populates="run",
        sa_relationship=relationship(
            "TrainingMetricSample",
            back_populates="run",
            cascade="all, delete-orphan",
        ),
    )
    alerts: list["TrainingAlert"] = Relationship(
        back_populates="run",
        sa_relationship=relationship(
            "TrainingAlert",
            back_populates="run",
            cascade="all, delete-orphan",
        ),
    )
    snapshots: list["TrainingSnapshot"] = Relationship(
        back_populates="run",
        sa_relationship=relationship(
            "TrainingSnapshot",
            back_populates="run",
            cascade="all, delete-orphan",
            foreign_keys="TrainingSnapshot.run_id",
        ),
    )
    resumed_from_snapshot: "TrainingSnapshot" | None = Relationship(
        sa_relationship=relationship(
            "TrainingSnapshot",
            foreign_keys="[TrainingRun.resumed_from_snapshot_id]",
            post_update=True,
        )
    )
    evaluations: list["EvaluationJob"] = Relationship(
        sa_relationship=relationship(
            "EvaluationJob",
            back_populates="training_run",
        )
    )


class TrainingEvent(SQLModel, table=True):
    """Structured log events captured during a training run."""

    __tablename__ = "training_events"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="training_runs.id", index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    level: str = Field(default="INFO", max_length=20)
    message: str = Field(max_length=2000)

    run: TrainingRun = Relationship(
        back_populates="events",
        sa_relationship=relationship("TrainingRun", back_populates="events"),
    )


class TrainingWizardDraft(SQLModel, table=True):
    """Persisted wizard draft per workspace and user."""

    __tablename__ = "training_wizard_drafts"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    payload_json: dict = Field(sa_column=Column(JSON, default=dict))
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    user: User = Relationship(sa_relationship=relationship("User"))


class TrainingMetricName(StrEnum):
    """Supported training metric keys for monitoring."""

    LOSS = "loss"
    PERPLEXITY = "perplexity"
    THROUGHPUT = "throughput"
    GPU_MEMORY = "gpu_memory"
    EVALUATION_BLEU = "evaluation_bleu"
    EVALUATION_ROUGE_L = "evaluation_rouge_l"
    EVALUATION_EXACT_MATCH = "evaluation_exact_match"
    EVALUATION_PERPLEXITY = "evaluation_perplexity"
    EVALUATION_FAILURE = "evaluation_failure"


class TrainingAlertOperator(StrEnum):
    """Comparison operators for alert thresholds."""

    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"


class TrainingAlertStatus(StrEnum):
    """Lifecycle status for a training alert."""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class TrainingMetricSample(SQLModel, table=True):
    """Captured metric sample for a training run."""

    __tablename__ = "training_metric_samples"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="training_runs.id", index=True)
    metric: TrainingMetricName = Field(
        sa_column=Column(Enum(TrainingMetricName, name="training_metric_name"))
    )
    value: float = Field(sa_column=Column(Float))
    recorded_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)

    run: TrainingRun = Relationship(
        sa_relationship=relationship(
            "TrainingRun",
            back_populates="metric_samples",
        )
    )


class TrainingAlertRule(SQLModel, table=True):
    """Threshold rule definition for training monitoring."""

    __tablename__ = "training_alert_rules"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    name: str = Field(max_length=200)
    metric: TrainingMetricName = Field(
        sa_column=Column(Enum(TrainingMetricName, name="training_alert_metric"))
    )
    operator: TrainingAlertOperator = Field(
        sa_column=Column(Enum(TrainingAlertOperator, name="training_alert_operator"))
    )
    threshold: float = Field(sa_column=Column(Float))
    cooldown_seconds: int = Field(default=300)
    is_active: bool = Field(default=True)
    channels_json: dict | None = Field(sa_column=Column(JSON, default=None))
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    creator: Optional[User] = Relationship(sa_relationship=relationship("User"))
    alerts: list["TrainingAlert"] = Relationship(
        back_populates="rule",
        sa_relationship=relationship(
            "TrainingAlert",
            back_populates="rule",
            cascade="all, delete-orphan",
        ),
    )


class TrainingAlert(SQLModel, table=True):
    """Alert instance triggered by threshold violation."""

    __tablename__ = "training_alerts"

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="training_alert_rules.id", index=True)
    run_id: int = Field(foreign_key="training_runs.id", index=True)
    value: float = Field(sa_column=Column(Float))
    status: TrainingAlertStatus = Field(
        sa_column=Column(Enum(TrainingAlertStatus, name="training_alert_status")),
        default=TrainingAlertStatus.TRIGGERED,
    )
    triggered_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    acknowledged_by: int | None = Field(default=None, foreign_key="users.id")
    acknowledged_at: datetime | None = Field(default=None)
    resolved_by: int | None = Field(default=None, foreign_key="users.id")
    resolved_at: datetime | None = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=1000)

    rule: TrainingAlertRule = Relationship(
        back_populates="alerts",
        sa_relationship=relationship("TrainingAlertRule", back_populates="alerts"),
    )
    run: TrainingRun = Relationship(
        sa_relationship=relationship("TrainingRun", back_populates="alerts")
    )


class TrainingSnapshotTriggerType(StrEnum):
    """Snapshot trigger source."""

    SCHEDULED = "scheduled"
    METRIC = "metric"
    MANUAL = "manual"


class TrainingSnapshot(SQLModel, table=True):
    """Snapshot metadata for training runs."""

    __tablename__ = "training_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    job_id: int = Field(foreign_key="training_jobs.id", index=True)
    run_id: int = Field(foreign_key="training_runs.id", index=True)
    path: str = Field(max_length=512)
    step: int | None = Field(default=None)
    epoch: int | None = Field(default=None)
    metrics_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    trigger_type: TrainingSnapshotTriggerType = Field(
        sa_column=Column(Enum(TrainingSnapshotTriggerType, name="training_snapshot_trigger_type"))
    )
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    notes: Optional[str] = Field(default=None, max_length=500)
    restored_at: datetime | None = Field(default=None)
    restored_by: int | None = Field(default=None, foreign_key="users.id")

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    job: TrainingJob = Relationship(sa_relationship=relationship("TrainingJob"))
    run: TrainingRun = Relationship(
        back_populates="snapshots",
        sa_relationship=relationship(
            "TrainingRun",
            back_populates="snapshots",
            foreign_keys="TrainingSnapshot.run_id",
        ),
    )

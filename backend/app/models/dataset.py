"""Dataset, dataset version, and cleaning job models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List

from sqlalchemy import Column, Enum, JSON
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel


class DatasetSourceType(StrEnum):
    """Supported dataset source types."""

    UPLOAD = "upload"
    EXTERNAL = "external"
    REFERENCE = "reference"


class DatasetStatus(StrEnum):
    """Lifecycle status for datasets."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DatasetVersionStatus(StrEnum):
    """Processing status for dataset versions."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataCleaningJobStatus(StrEnum):
    """Execution status for data cleaning jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QualityEvaluationStatus(StrEnum):
    """Execution status for quality evaluation jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CleaningStepType(StrEnum):
    """Supported transformation step types for cleaning templates."""

    DEDUPLICATE = "deduplicate"
    DROP_NOISE = "drop_noise"
    MASK_FIELD = "mask_field"
    NORMALIZE_CASE = "normalize_case"
    TRIM_WHITESPACE = "trim_whitespace"


class DatasetCleaningTemplate(SQLModel, table=True):
    """Reusable cleaning template scoped to workspace."""

    __tablename__ = "dataset_cleaning_templates"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True)
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=1024)
    is_active: bool = Field(default=True)
    version: int = Field(default=1, description="Template revision number")
    steps: list[dict] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class DatasetCleaningAssignment(SQLModel, table=True):
    """Mapping between dataset and its selected cleaning template."""

    __tablename__ = "dataset_cleaning_assignments"

    dataset_id: int = Field(foreign_key="datasets.id", primary_key=True)
    template_id: int = Field(foreign_key="dataset_cleaning_templates.id")
    enabled: bool = Field(default=True)
    assigned_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Dataset(SQLModel, table=True):
    """Dataset metadata stored at workspace scope."""

    __tablename__ = "datasets"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True)
    name: str = Field(max_length=200, index=True)
    description: str | None = Field(default=None)
    source_type: DatasetSourceType = Field(
        sa_column=Column(Enum(DatasetSourceType, name="dataset_source_type")),
        default=DatasetSourceType.UPLOAD,
    )
    source_uri: str | None = Field(default=None, max_length=1024)
    storage_path: str | None = Field(default=None, max_length=1024)
    data_type: str | None = Field(default=None, max_length=100)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size_bytes: int | None = Field(default=None)
    checksum_sha256: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    notes: str | None = Field(default=None)
    status: DatasetStatus = Field(
        default=DatasetStatus.ACTIVE,
        sa_column=Column(Enum(DatasetStatus, name="dataset_status")),
    )
    reference_dataset_id: int | None = Field(default=None, foreign_key="datasets.id")
    created_by: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    versions: List["DatasetVersion"] = Relationship(
        back_populates="dataset",
        sa_relationship=relationship(
            "DatasetVersion",
            back_populates="dataset",
            cascade="all, delete-orphan",
        ),
    )


class DatasetVersion(SQLModel, table=True):
    """Dataset version metadata for cleaning runs."""

    __tablename__ = "dataset_versions"

    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="datasets.id", index=True)
    version: int = Field(index=True)
    status: DatasetVersionStatus = Field(
        default=DatasetVersionStatus.PENDING,
        sa_column=Column(Enum(DatasetVersionStatus, name="dataset_version_status")),
    )
    location_uri: str | None = Field(default=None, max_length=1024)
    stats_json: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    quality_summary_path: str | None = Field(default=None, max_length=1024)
    quality_report_manifest: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    created_by: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    dataset: "Dataset" = Relationship(
        back_populates="versions",
        sa_relationship=relationship(
            "Dataset",
            back_populates="versions",
        ),
    )
    cleaning_jobs: List["DataCleaningJob"] = Relationship(
        back_populates="dataset_version",
        sa_relationship=relationship(
            "DataCleaningJob",
            back_populates="dataset_version",
            cascade="all, delete-orphan",
        ),
    )
    quality_jobs: List["QualityEvaluationJob"] = Relationship(
        back_populates="dataset_version",
        sa_relationship=relationship(
            "QualityEvaluationJob",
            back_populates="dataset_version",
            cascade="all, delete-orphan",
        ),
    )
    format_versions: List["DatasetFormatVersion"] = Relationship(
        back_populates="dataset_version",
        sa_relationship=relationship(
            "DatasetFormatVersion",
            back_populates="dataset_version",
            cascade="all, delete-orphan",
        ),
    )


class DataCleaningJob(SQLModel, table=True):
    """Asynchronous cleaning job tracking for dataset versions."""

    __tablename__ = "data_cleaning_jobs"

    id: int | None = Field(default=None, primary_key=True)
    dataset_version_id: int = Field(foreign_key="dataset_versions.id", index=True)
    status: DataCleaningJobStatus = Field(
        default=DataCleaningJobStatus.PENDING,
        sa_column=Column(Enum(DataCleaningJobStatus, name="data_cleaning_job_status")),
    )
    template_id: int | None = Field(default=None, foreign_key="dataset_cleaning_templates.id")
    template_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    logs_path: str | None = Field(default=None, max_length=1024)
    error_message: str | None = Field(default=None)
    summary_path: str | None = Field(default=None, max_length=1024)
    export_manifest: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)

    dataset_version: "DatasetVersion" = Relationship(
        back_populates="cleaning_jobs",
        sa_relationship=relationship(
            "DatasetVersion",
            back_populates="cleaning_jobs",
        ),
    )
class QualityEvaluationJob(SQLModel, table=True):
    """Quality evaluation job tracking for dataset versions."""

    __tablename__ = "quality_evaluation_jobs"

    id: int | None = Field(default=None, primary_key=True)
    dataset_version_id: int = Field(foreign_key="dataset_versions.id", index=True)
    status: QualityEvaluationStatus = Field(
        default=QualityEvaluationStatus.PENDING,
        sa_column=Column(Enum(QualityEvaluationStatus, name="quality_evaluation_status")),
    )
    logs_path: str | None = Field(default=None, max_length=1024)
    summary_path: str | None = Field(default=None, max_length=1024)
    export_manifest: dict | None = Field(default=None, sa_column=Column(JSON, default=None))
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)

    dataset_version: "DatasetVersion" = Relationship(
        back_populates="quality_jobs",
        sa_relationship=relationship(
            "DatasetVersion",
            back_populates="quality_jobs",
        ),
    )


class DatasetFormatType(StrEnum):
    """Supported standardisation target formats."""

    JSONL = "jsonl"
    SFT = "sft"
    PARQUET = "parquet"


class DatasetFormatStatus(StrEnum):
    """Processing status for format conversions."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DatasetFormatVersion(SQLModel, table=True):
    """Standardised format artefact for a dataset version."""

    __tablename__ = "dataset_format_versions"

    id: int | None = Field(default=None, primary_key=True)
    dataset_version_id: int = Field(foreign_key="dataset_versions.id", index=True)
    format: DatasetFormatType = Field(
        sa_column=Column(Enum(DatasetFormatType, name="dataset_format_type"))
    )
    status: DatasetFormatStatus = Field(
        default=DatasetFormatStatus.PENDING,
        sa_column=Column(Enum(DatasetFormatStatus, name="dataset_format_status")),
    )
    path: str | None = Field(default=None, max_length=1024)
    logs_path: str | None = Field(default=None, max_length=1024)
    checksum_sha256: str | None = Field(default=None, max_length=128)
    file_size_bytes: int | None = Field(default=None)
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    error_message: str | None = Field(default=None)

    dataset_version: "DatasetVersion" = Relationship(
        back_populates="format_versions",
        sa_relationship=relationship(
            "DatasetVersion",
            back_populates="format_versions",
        ),
    )

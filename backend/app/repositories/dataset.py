"""Repositories for dataset and cleaning job management."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import (
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetStatus,
    DatasetVersion,
    DatasetVersionStatus,
)


class DatasetRepository:
    """Encapsulate dataset persistence logic."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, dataset_id: int) -> Dataset | None:
        return self._session.get(Dataset, dataset_id)

    def get_by_name(self, *, workspace_id: int, name: str) -> Dataset | None:
        statement = select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.name == name,
        )
        return self._session.exec(statement).first()

    def list_for_workspace(self, workspace_id: int) -> Sequence[Dataset]:
        statement = (
            select(Dataset)
            .where(Dataset.workspace_id == workspace_id)
            .order_by(Dataset.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def create(self, dataset: Dataset) -> Dataset:
        now = datetime.utcnow()
        dataset.created_at = now
        dataset.updated_at = now
        self._session.add(dataset)
        self._session.flush()
        self._session.refresh(dataset)
        return dataset

    def update(self, dataset: Dataset, *, status: DatasetStatus | None = None) -> Dataset:
        if status is not None:
            dataset.status = status
        dataset.updated_at = datetime.utcnow()
        self._session.add(dataset)
        self._session.flush()
        self._session.refresh(dataset)
        return dataset


class DatasetVersionRepository:
    """Dataset version persistence helpers."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_dataset(self, dataset_id: int) -> Sequence[DatasetVersion]:
        statement = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get_latest_version_number(self, dataset_id: int) -> int | None:
        statement = (
            select(DatasetVersion.version)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.desc())
        )
        return self._session.exec(statement).first()

    def get(self, dataset_version_id: int) -> DatasetVersion | None:
        return self._session.get(DatasetVersion, dataset_version_id)

    def create(self, version: DatasetVersion) -> DatasetVersion:
        now = datetime.utcnow()
        version.created_at = now
        version.updated_at = now
        self._session.add(version)
        self._session.flush()
        self._session.refresh(version)
        return version

    def update_status(
        self,
        version: DatasetVersion,
        *,
        status: DatasetVersionStatus,
        location_uri: str | None = None,
        stats_json: dict | None = None,
    ) -> DatasetVersion:
        version.status = status
        if location_uri is not None:
            version.location_uri = location_uri
        if stats_json is not None:
            existing = version.stats_json or {}
            merged = {**existing, **stats_json}
            version.stats_json = merged
        version.updated_at = datetime.utcnow()
        self._session.add(version)
        self._session.flush()
        self._session.refresh(version)
        return version


class DataCleaningJobRepository:
    """Manage data cleaning job persistence."""

    def __init__(self, session: Session):
        self._session = session

    def get_latest_job_for_workspace(
        self, workspace_id: int
    ) -> tuple[DataCleaningJob, DatasetVersion, Dataset] | None:
        """Return the most recent cleaning job linked to the workspace, if any."""
        statement = (
            select(DataCleaningJob, DatasetVersion, Dataset)
            .join(DatasetVersion, DataCleaningJob.dataset_version_id == DatasetVersion.id)
            .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
            .where(Dataset.workspace_id == workspace_id)
            .order_by(DataCleaningJob.created_at.desc())
        )
        result = self._session.exec(statement).first()
        if result is None:
            return None
        job, version, dataset = result
        return job, version, dataset

    def create(self, job: DataCleaningJob) -> DataCleaningJob:
        now = datetime.utcnow()
        job.created_at = now
        job.updated_at = now
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

    def get_by_version(self, dataset_version_id: int) -> DataCleaningJob | None:
        statement = (
            select(DataCleaningJob)
            .where(DataCleaningJob.dataset_version_id == dataset_version_id)
            .order_by(DataCleaningJob.created_at.desc())
        )
        return self._session.exec(statement).first()

    def update_status(
        self,
        job: DataCleaningJob,
        *,
        status: DataCleaningJobStatus,
        error_message: str | None = None,
        logs_path: str | None = None,
        mark_started: bool = False,
        mark_finished: bool = False,
        summary_path: str | None = None,
        export_manifest: dict | None = None,
    ) -> DataCleaningJob:
        now = datetime.utcnow()
        job.status = status
        if error_message is not None:
            job.error_message = error_message
        if logs_path is not None:
            job.logs_path = logs_path
        if summary_path is not None:
            job.summary_path = summary_path
        if export_manifest is not None:
            job.export_manifest = export_manifest
        if mark_started:
            job.started_at = now
        if mark_finished:
            job.finished_at = now
        job.updated_at = now
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

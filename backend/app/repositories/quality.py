"""Repositories for quality evaluation jobs."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import QualityEvaluationJob, QualityEvaluationStatus


class QualityEvaluationJobRepository:
    """Persist and query quality evaluation jobs."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, job: QualityEvaluationJob) -> QualityEvaluationJob:
        now = datetime.utcnow()
        job.created_at = now
        job.updated_at = now
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

    def get(self, job_id: int) -> QualityEvaluationJob | None:
        return self._session.get(QualityEvaluationJob, job_id)

    def get_by_version(self, dataset_version_id: int) -> QualityEvaluationJob | None:
        statement = (
            select(QualityEvaluationJob)
            .where(QualityEvaluationJob.dataset_version_id == dataset_version_id)
            .order_by(QualityEvaluationJob.created_at.desc())
        )
        return self._session.exec(statement).first()

    def update_status(
        self,
        job: QualityEvaluationJob,
        *,
        status: QualityEvaluationStatus,
        error_message: str | None = None,
        logs_path: str | None = None,
        summary_path: str | None = None,
        export_manifest: dict | None = None,
        mark_started: bool = False,
        mark_finished: bool = False,
    ) -> QualityEvaluationJob:
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

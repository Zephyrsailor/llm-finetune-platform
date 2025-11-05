"""Repositories for evaluation templates and jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import (
    EvaluationTemplate,
    EvaluationJob,
    EvaluationJobStatus,
    EvaluationTaskType,
    EvaluationFeedback,
    EvaluationFeedbackKind,
    EvaluationFeedbackStatus,
)


class EvaluationTemplateRepository:
    """Persist and query evaluation templates."""

    def __init__(self, session: Session):
        self._session = session

    def list_all(self) -> Sequence[EvaluationTemplate]:
        statement = select(EvaluationTemplate).order_by(EvaluationTemplate.updated_at.desc())
        return tuple(self._session.exec(statement).all())

    def list_for_workspace(self, workspace_id: int | None) -> Sequence[EvaluationTemplate]:
        statement = (
            select(EvaluationTemplate)
            .where(
                (EvaluationTemplate.workspace_id == workspace_id)
                | (EvaluationTemplate.workspace_id.is_(None))
            )
            .order_by(EvaluationTemplate.updated_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get(self, template_id: int) -> EvaluationTemplate | None:
        return self._session.get(EvaluationTemplate, template_id)

    def get_by_key(self, key: str) -> EvaluationTemplate | None:
        statement = select(EvaluationTemplate).where(EvaluationTemplate.key == key)
        return self._session.exec(statement).first()

    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None,
        task_type: EvaluationTaskType,
        metrics: list[str],
        config: dict | None,
        is_builtin: bool,
        workspace_id: int | None,
    ) -> EvaluationTemplate:
        now = datetime.utcnow()
        template = EvaluationTemplate(
            key=key,
            name=name,
            description=description,
            task_type=task_type,
            metrics=list(metrics),
            config_json=config or {},
            is_builtin=is_builtin,
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template

    def update_timestamp(self, template: EvaluationTemplate) -> EvaluationTemplate:
        template.updated_at = datetime.utcnow()
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template


class EvaluationJobRepository:
    """Persist and query evaluation jobs."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(
        self,
        workspace_id: int,
        *,
        training_run_id: int | None = None,
    ) -> Sequence[EvaluationJob]:
        statement = select(EvaluationJob).where(EvaluationJob.workspace_id == workspace_id)
        if training_run_id is not None:
            statement = statement.where(EvaluationJob.training_run_id == training_run_id)
        statement = statement.order_by(EvaluationJob.created_at.desc())
        return tuple(self._session.exec(statement).all())

    def get(self, job_id: int) -> EvaluationJob | None:
        return self._session.get(EvaluationJob, job_id)

    def list_for_training_run(self, training_run_id: int) -> Sequence[EvaluationJob]:
        statement = (
            select(EvaluationJob)
            .where(EvaluationJob.training_run_id == training_run_id)
            .order_by(EvaluationJob.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def find_by_run_and_template(
        self,
        *,
        training_run_id: int,
        evaluation_template_id: int,
    ) -> EvaluationJob | None:
        statement = (
            select(EvaluationJob)
            .where(EvaluationJob.training_run_id == training_run_id)
            .where(EvaluationJob.evaluation_template_id == evaluation_template_id)
            .order_by(EvaluationJob.created_at.desc())
        )
        return self._session.exec(statement).first()

    def create(self, job: EvaluationJob) -> EvaluationJob:
        now = datetime.utcnow()
        job.created_at = now
        job.updated_at = now
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

    def update(
        self,
        job: EvaluationJob,
        *,
        status: EvaluationJobStatus | None = None,
        dataset_path: str | None = None,
        artifact_path: str | None = None,
        report_path: str | None = None,
        metrics_json: dict | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> EvaluationJob:
        if status is not None:
            job.status = status
        if dataset_path is not None:
            job.dataset_path = dataset_path
        if artifact_path is not None:
            job.artifact_path = artifact_path
        if report_path is not None:
            job.report_path = report_path
        if metrics_json is not None:
            job.metrics_json = metrics_json
        if error_message is not None:
            job.error_message = error_message
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at
        job.updated_at = datetime.utcnow()
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job


class EvaluationFeedbackRepository:
    """Persist and query evaluation feedback entries."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, feedback_id: int) -> EvaluationFeedback | None:
        return self._session.get(EvaluationFeedback, feedback_id)

    def list_for_job(
        self,
        job_id: int,
    ) -> Sequence[EvaluationFeedback]:
        statement = (
            select(EvaluationFeedback)
            .where(EvaluationFeedback.evaluation_job_id == job_id)
            .order_by(EvaluationFeedback.created_at.asc())
        )
        return tuple(self._session.exec(statement).all())

    def list_open_for_project(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        limit: int,
        kind: EvaluationFeedbackKind | None = None,
    ) -> Sequence[EvaluationFeedback]:
        statement = select(EvaluationFeedback).where(EvaluationFeedback.workspace_id == workspace_id)
        if project_id is not None:
            statement = statement.where(EvaluationFeedback.project_id == project_id)
        statement = statement.where(EvaluationFeedback.status == EvaluationFeedbackStatus.OPEN)
        if kind is not None:
            statement = statement.where(EvaluationFeedback.kind == kind)
        statement = statement.order_by(EvaluationFeedback.created_at.desc()).limit(limit)
        return tuple(self._session.exec(statement).all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        evaluation_job_id: int,
        training_run_id: int | None,
        kind: EvaluationFeedbackKind,
        status: EvaluationFeedbackStatus,
        body: str,
        tags: list[str],
        metric_name: str | None,
        metric_value: float | None,
        created_by: int,
    ) -> EvaluationFeedback:
        now = datetime.utcnow()
        entry = EvaluationFeedback(
            workspace_id=workspace_id,
            project_id=project_id,
            evaluation_job_id=evaluation_job_id,
            training_run_id=training_run_id,
            kind=kind,
            status=status,
            body=body,
            tags=list(tags),
            metric_name=metric_name,
            metric_value=metric_value,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def update(
        self,
        entry: EvaluationFeedback,
        *,
        body: str | None = None,
        status: EvaluationFeedbackStatus | None = None,
        tags: list[str] | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
        updated_by: int | None = None,
        resolved_by: int | None = None,
        resolved_at: datetime | None = None,
    ) -> EvaluationFeedback:
        if body is not None:
            entry.body = body
        if status is not None:
            entry.status = status
        if tags is not None:
            entry.tags = list(tags)
        if metric_name is not None or metric_value is not None:
            entry.metric_name = metric_name
            entry.metric_value = metric_value
        entry.updated_at = datetime.utcnow()
        if updated_by is not None:
            entry.updated_by = updated_by
        entry.resolved_by = resolved_by
        entry.resolved_at = resolved_at
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def delete(self, entry: EvaluationFeedback) -> None:
        self._session.delete(entry)
        self._session.flush()

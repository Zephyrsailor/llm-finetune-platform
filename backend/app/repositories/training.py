"""Repository helpers for training templates, jobs, runs, and events."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import (
    TrainingEvent,
    TrainingJob,
    TrainingJobStatus,
    TrainingRun,
    TrainingTemplate,
    TrainingAdapterType,
    TrainingWizardDraft,
    TrainingMetricSample,
    TrainingMetricName,
    TrainingAlertRule,
    TrainingAlertOperator,
    TrainingAlert,
    TrainingAlertStatus,
    TrainingSnapshot,
    TrainingSnapshotTriggerType,
)


class TrainingTemplateRepository:
    """Persist and query training templates."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(self, workspace_id: int) -> Sequence[TrainingTemplate]:
        statement = (
            select(TrainingTemplate)
            .where(TrainingTemplate.workspace_id == workspace_id)
            .order_by(TrainingTemplate.updated_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get(self, template_id: int) -> TrainingTemplate | None:
        return self._session.get(TrainingTemplate, template_id)

    def create(
        self,
        *,
        workspace_id: int,
        name: str,
        base_model: str,
        adapter_type: TrainingAdapterType,
        params: dict,
        description: str | None,
        created_by: int | None,
        is_builtin: bool = False,
    ) -> TrainingTemplate:
        now = datetime.utcnow()
        template = TrainingTemplate(
            workspace_id=workspace_id,
            name=name,
            description=description,
            base_model=base_model,
            adapter_type=adapter_type,
            params_json=params,
            is_builtin=is_builtin,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template

    def update(
        self,
        template: TrainingTemplate,
        *,
        name: str | None = None,
        description: str | None = None,
        base_model: str | None = None,
        adapter_type: TrainingAdapterType | None = None,
        params: dict | None = None,
        is_builtin: bool | None = None,
    ) -> TrainingTemplate:
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if base_model is not None:
            template.base_model = base_model
        if adapter_type is not None:
            template.adapter_type = adapter_type
        if params is not None:
            template.params_json = params
        if is_builtin is not None:
            template.is_builtin = is_builtin
        template.updated_at = datetime.utcnow()
        self._session.add(template)
        self._session.flush()
        self._session.refresh(template)
        return template

    def delete(self, template: TrainingTemplate) -> None:
        self._session.delete(template)
        self._session.flush()


class TrainingJobRepository:
    """Persist and query training jobs."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, job_id: int) -> TrainingJob | None:
        return self._session.get(TrainingJob, job_id)

    def list_for_workspace(self, workspace_id: int) -> Sequence[TrainingJob]:
        statement = (
            select(TrainingJob)
            .where(TrainingJob.workspace_id == workspace_id)
            .order_by(TrainingJob.scheduled_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def create(self, job: TrainingJob) -> TrainingJob:
        now = datetime.utcnow()
        job.scheduled_at = now
        job.started_at = job.started_at or None
        job.finished_at = job.finished_at or None
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

    def update_status(
        self,
        job: TrainingJob,
        *,
        status: TrainingJobStatus,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error_message: str | None = None,
    ) -> TrainingJob:
        job.status = status
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at
        if error_message is not None:
            job.error_message = error_message
        self._session.add(job)
        self._session.flush()
        self._session.refresh(job)
        return job

    def exists_for_template(self, template_id: int) -> bool:
        statement = (
            select(TrainingJob.id)
            .where(TrainingJob.training_template_id == template_id)
            .limit(1)
        )
        result = self._session.exec(statement).first()
        return result is not None


class TrainingRunRepository:
    """Persist and query training runs."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, run_id: int) -> TrainingRun | None:
        return self._session.get(TrainingRun, run_id)

    def get_latest_for_job(self, job_id: int) -> TrainingRun | None:
        statement = (
            select(TrainingRun)
            .where(TrainingRun.job_id == job_id)
            .order_by(TrainingRun.started_at.desc())
        )
        return self._session.exec(statement).first()

    def create(self, run: TrainingRun) -> TrainingRun:
        if not run.started_at:
            run.started_at = datetime.utcnow()
        self._session.add(run)
        self._session.flush()
        self._session.refresh(run)
        return run

    def update(
        self,
        run: TrainingRun,
        *,
        status: TrainingJobStatus | None = None,
        finished_at: datetime | None = None,
        metrics_json: dict | None = None,
        artifact_uri: str | None = None,
        exit_code: int | None = None,
        metadata_json: dict | None = None,
    ) -> TrainingRun:
        if status is not None:
            run.status = status
        if finished_at is not None:
            run.finished_at = finished_at
        if metrics_json is not None:
            run.metrics_json = metrics_json
        if artifact_uri is not None:
            run.artifact_uri = artifact_uri
        if exit_code is not None:
            run.exit_code = exit_code
        if metadata_json is not None:
            run.metadata_json = metadata_json
        self._session.add(run)
        self._session.flush()
        self._session.refresh(run)
        return run


class TrainingEventRepository:
    """Persist and query training run events."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_run(self, run_id: int) -> Sequence[TrainingEvent]:
        statement = (
            select(TrainingEvent)
            .where(TrainingEvent.run_id == run_id)
            .order_by(TrainingEvent.timestamp.asc())
        )
        return tuple(self._session.exec(statement).all())

    def create(
        self,
        *,
        run_id: int,
        level: str,
        message: str,
        timestamp: datetime | None = None,
    ) -> TrainingEvent:
        event = TrainingEvent(
            run_id=run_id,
            level=level,
            message=message,
            timestamp=timestamp or datetime.utcnow(),
        )
        self._session.add(event)
        self._session.flush()
        self._session.refresh(event)
        return event


class TrainingWizardDraftRepository:
    """Persist and retrieve training wizard drafts."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, *, workspace_id: int, user_id: int) -> TrainingWizardDraft | None:
        statement = (
            select(TrainingWizardDraft)
            .where(
                TrainingWizardDraft.workspace_id == workspace_id,
                TrainingWizardDraft.user_id == user_id,
            )
        )
        return self._session.exec(statement).first()

    def upsert(
        self,
        *,
        workspace_id: int,
        user_id: int,
        payload: dict,
    ) -> TrainingWizardDraft:
        draft = self.get(workspace_id=workspace_id, user_id=user_id)
        now = datetime.utcnow()
        if draft is None:
            draft = TrainingWizardDraft(
                workspace_id=workspace_id,
                user_id=user_id,
                payload_json=payload,
                updated_at=now,
            )
            self._session.add(draft)
        else:
            draft.payload_json = payload
            draft.updated_at = now
            self._session.add(draft)
        self._session.flush()
        self._session.refresh(draft)
        return draft

    def delete(self, *, workspace_id: int, user_id: int) -> None:
        draft = self.get(workspace_id=workspace_id, user_id=user_id)
        if draft is None:
            return
        self._session.delete(draft)
        self._session.flush()


class TrainingMetricRepository:
    """Persist and retrieve training metric samples."""

    def __init__(self, session: Session):
        self._session = session

    def record(
        self,
        *,
        run_id: int,
        metric: TrainingMetricName,
        value: float,
        recorded_at: datetime | None = None,
    ) -> TrainingMetricSample:
        sample = TrainingMetricSample(
            run_id=run_id,
            metric=metric,
            value=value,
            recorded_at=recorded_at or datetime.utcnow(),
        )
        self._session.add(sample)
        self._session.flush()
        self._session.refresh(sample)
        return sample

    def list_for_run(self, run_id: int) -> Sequence[TrainingMetricSample]:
        statement = (
            select(TrainingMetricSample)
            .where(TrainingMetricSample.run_id == run_id)
            .order_by(TrainingMetricSample.recorded_at.asc())
        )
        return tuple(self._session.exec(statement).all())

    def latest_by_metric_for_run(self, run_id: int) -> dict[TrainingMetricName, TrainingMetricSample | None]:
        latest: dict[TrainingMetricName, TrainingMetricSample | None] = {}
        for metric_name in TrainingMetricName:
            statement = (
                select(TrainingMetricSample)
                .where(
                    TrainingMetricSample.run_id == run_id,
                    TrainingMetricSample.metric == metric_name,
                )
                .order_by(TrainingMetricSample.recorded_at.desc())
            )
            latest[metric_name] = self._session.exec(statement).first()
        return latest


class TrainingAlertRuleRepository:
    """Persist and query training alert rules."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(self, workspace_id: int) -> Sequence[TrainingAlertRule]:
        statement = (
            select(TrainingAlertRule)
            .where(TrainingAlertRule.workspace_id == workspace_id)
            .order_by(TrainingAlertRule.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def list_active_for_workspace(self, workspace_id: int) -> Sequence[TrainingAlertRule]:
        statement = (
            select(TrainingAlertRule)
            .where(
                TrainingAlertRule.workspace_id == workspace_id,
                TrainingAlertRule.is_active.is_(True),
            )
            .order_by(TrainingAlertRule.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get(self, rule_id: int) -> TrainingAlertRule | None:
        return self._session.get(TrainingAlertRule, rule_id)

    def get_by_workspace_and_name(self, workspace_id: int, name: str) -> TrainingAlertRule | None:
        statement = (
            select(TrainingAlertRule)
            .where(
                TrainingAlertRule.workspace_id == workspace_id,
                TrainingAlertRule.name == name,
            )
            .order_by(TrainingAlertRule.created_at.desc())
        )
        return self._session.exec(statement).first()

    def create(
        self,
        *,
        workspace_id: int,
        name: str,
        metric: TrainingMetricName,
        operator: TrainingAlertOperator,
        threshold: float,
        cooldown_seconds: int,
        channels: dict | None,
        created_by: int | None,
    ) -> TrainingAlertRule:
        now = datetime.utcnow()
        rule = TrainingAlertRule(
            workspace_id=workspace_id,
            name=name,
            metric=metric,
            operator=operator,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            is_active=True,
            channels_json=channels,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)
        return rule

    def update(
        self,
        rule: TrainingAlertRule,
        *,
        name: str | None = None,
        operator: TrainingAlertOperator | None = None,
        threshold: float | None = None,
        cooldown_seconds: int | None = None,
        is_active: bool | None = None,
        channels: dict | None = None,
    ) -> TrainingAlertRule:
        if name is not None:
            rule.name = name
        if operator is not None:
            rule.operator = operator
        if threshold is not None:
            rule.threshold = threshold
        if cooldown_seconds is not None:
            rule.cooldown_seconds = cooldown_seconds
        if is_active is not None:
            rule.is_active = is_active
        if channels is not None:
            rule.channels_json = channels
        rule.updated_at = datetime.utcnow()
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)
        return rule


class TrainingAlertRepository:
    """Persist and query training alerts."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        rule_id: int,
        run_id: int,
        value: float,
        triggered_at: datetime | None = None,
    ) -> TrainingAlert:
        alert = TrainingAlert(
            rule_id=rule_id,
            run_id=run_id,
            value=value,
            triggered_at=triggered_at or datetime.utcnow(),
            status=TrainingAlertStatus.TRIGGERED,
        )
        self._session.add(alert)
        self._session.flush()
        self._session.refresh(alert)
        return alert

    def list_recent_for_workspace(self, workspace_id: int, limit: int = 50) -> Sequence[TrainingAlert]:
        statement = (
            select(TrainingAlert)
            .join(TrainingAlertRule)
            .where(TrainingAlertRule.workspace_id == workspace_id)
            .order_by(TrainingAlert.triggered_at.desc())
            .limit(limit)
        )
        return tuple(self._session.exec(statement).all())

    def list_for_run(self, run_id: int) -> Sequence[TrainingAlert]:
        statement = (
            select(TrainingAlert)
            .where(TrainingAlert.run_id == run_id)
            .order_by(TrainingAlert.triggered_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get(self, alert_id: int) -> TrainingAlert | None:
        return self._session.get(TrainingAlert, alert_id)

    def get_latest_for_rule(self, rule_id: int, run_id: int) -> TrainingAlert | None:
        statement = (
            select(TrainingAlert)
            .where(
                TrainingAlert.rule_id == rule_id,
                TrainingAlert.run_id == run_id,
            )
            .order_by(TrainingAlert.triggered_at.desc())
        )
        return self._session.exec(statement).first()

    def update_status(
        self,
        alert: TrainingAlert,
        *,
        status: TrainingAlertStatus,
        actor_id: int | None,
        notes: str | None = None,
    ) -> TrainingAlert:
        now = datetime.utcnow()
        alert.status = status
        if status == TrainingAlertStatus.ACKNOWLEDGED:
            alert.acknowledged_by = actor_id
            alert.acknowledged_at = now
        if status == TrainingAlertStatus.RESOLVED:
            alert.resolved_by = actor_id
            alert.resolved_at = now
        if notes is not None:
            alert.notes = notes
        self._session.add(alert)
        self._session.flush()
        self._session.refresh(alert)
        return alert


class TrainingSnapshotRepository:
    """Persist and query training snapshots."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        workspace_id: int,
        job_id: int,
        run_id: int,
        path: str,
        trigger_type: TrainingSnapshotTriggerType,
        step: int | None = None,
        epoch: int | None = None,
        metrics_json: dict | None = None,
        created_by: int | None = None,
        notes: str | None = None,
    ) -> TrainingSnapshot:
        snapshot = TrainingSnapshot(
            workspace_id=workspace_id,
            job_id=job_id,
            run_id=run_id,
            path=path,
            trigger_type=trigger_type,
            step=step,
            epoch=epoch,
            metrics_json=metrics_json,
            created_by=created_by,
            notes=notes,
        )
        self._session.add(snapshot)
        self._session.flush()
        self._session.refresh(snapshot)
        return snapshot

    def get(self, snapshot_id: int) -> TrainingSnapshot | None:
        statement = select(TrainingSnapshot).where(TrainingSnapshot.id == snapshot_id)
        return self._session.exec(statement).first()

    def list_for_run(self, run_id: int) -> Sequence[TrainingSnapshot]:
        statement = (
            select(TrainingSnapshot)
            .where(TrainingSnapshot.run_id == run_id)
            .order_by(TrainingSnapshot.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def list_for_workspace(self, workspace_id: int) -> Sequence[TrainingSnapshot]:
        statement = (
            select(TrainingSnapshot)
            .where(TrainingSnapshot.workspace_id == workspace_id)
            .order_by(TrainingSnapshot.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def mark_restored(self, snapshot: TrainingSnapshot, *, restored_by: int | None) -> TrainingSnapshot:
        snapshot.restored_at = datetime.utcnow()
        snapshot.restored_by = restored_by
        self._session.add(snapshot)
        self._session.flush()
        self._session.refresh(snapshot)
        return snapshot

    def list_recent_for_workspace(self, workspace_id: int, limit: int = 50) -> Sequence[TrainingSnapshot]:
        statement = (
            select(TrainingSnapshot)
            .where(TrainingSnapshot.workspace_id == workspace_id)
            .order_by(TrainingSnapshot.created_at.desc())
            .limit(limit)
        )
        return tuple(self._session.exec(statement).all())

    def delete(self, snapshot: TrainingSnapshot) -> None:
        self._session.delete(snapshot)
        self._session.flush()

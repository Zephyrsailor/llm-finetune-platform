"""Training monitoring service: metrics, alert rules, and alerts."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlmodel import Session, select

from app.models import (
    TrainingAlert,
    TrainingAlertOperator,
    TrainingAlertRule,
    TrainingAlertStatus,
    TrainingMetricName,
    TrainingMetricSample,
    TrainingRun,
    TrainingJob,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.training import (
    TrainingAlertRepository,
    TrainingAlertRuleRepository,
    TrainingJobRepository,
    TrainingMetricRepository,
    TrainingRunRepository,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


class TrainingMonitoringService:
    """Domain service for training metrics and alert orchestration."""

    def __init__(self, session: Session):
        self._session = session
        self._metrics = TrainingMetricRepository(session)
        self._alert_rules = TrainingAlertRuleRepository(session)
        self._alerts = TrainingAlertRepository(session)
        self._runs = TrainingRunRepository(session)
        self._jobs = TrainingJobRepository(session)
        self._audit = AuditLogRepository(session)
        self._permissions = PermissionService(session)

    # ------------------------------------------------------------------ #
    # Metrics recording & retrieval
    # ------------------------------------------------------------------ #

    def record_metric(
        self,
        *,
        run: TrainingRun,
        metric: TrainingMetricName,
        value: float,
        recorded_at: datetime | None = None,
    ) -> TrainingMetricSample:
        """Persist a metric sample and evaluate alert rules."""
        sample = self._metrics.record(
            run_id=run.id,
            metric=metric,
            value=value,
            recorded_at=recorded_at,
        )
        job = self._jobs.get(run.job_id)
        if job and job.workspace_id:
            self._evaluate_rules(
                workspace_id=job.workspace_id,
                run=run,
                metric=metric,
                value=value,
                triggered_at=sample.recorded_at,
            )
        return sample

    def ensure_can_view(self, workspace_id: int, current_user) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

    def get_run(self, run_id: int) -> TrainingRun | None:
        return self._runs.get(run_id)

    def get_job(self, job_id: int) -> TrainingJob | None:
        return self._jobs.get(job_id)

    def get_alert_rule(self, rule_id: int) -> TrainingAlertRule | None:
        return self._alert_rules.get(rule_id)

    def get_alert(self, alert_id: int) -> TrainingAlert | None:
        return self._alerts.get(alert_id)

    def list_runs(self, workspace_id: int) -> Sequence[TrainingRun]:
        statement = (
            select(TrainingRun)
            .join(TrainingJob)
            .where(TrainingJob.workspace_id == workspace_id)
            .order_by(TrainingRun.started_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def latest_metrics_for_run(self, run_id: int) -> dict[TrainingMetricName, TrainingMetricSample | None]:
        return self._metrics.latest_by_metric_for_run(run_id)

    def list_metric_samples(self, run_id: int) -> Sequence[TrainingMetricSample]:
        return self._metrics.list_for_run(run_id)

    # ------------------------------------------------------------------ #
    # Alert rule management
    # ------------------------------------------------------------------ #

    def list_alert_rules(self, workspace_id: int) -> Sequence[TrainingAlertRule]:
        return self._alert_rules.list_for_workspace(workspace_id)

    def create_alert_rule(
        self,
        *,
        workspace_id: int,
        name: str,
        metric: TrainingMetricName,
        operator: TrainingAlertOperator,
        threshold: float,
        cooldown_seconds: int,
        channels: dict | None,
        current_user,
    ) -> TrainingAlertRule:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        rule = self._alert_rules.create(
            workspace_id=workspace_id,
            name=name,
            metric=metric,
            operator=operator,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            channels=channels,
            created_by=current_user.id if current_user else None,
        )
        self._audit.record(
            event_type="training.alert_rule.created",
            user_id=current_user.id if current_user else None,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace_id,
                "rule_id": rule.id,
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
            },
        )
        return rule

    def update_alert_rule(
        self,
        *,
        rule: TrainingAlertRule,
        name: str | None = None,
        operator: TrainingAlertOperator | None = None,
        threshold: float | None = None,
        cooldown_seconds: int | None = None,
        is_active: bool | None = None,
        channels: dict | None = None,
        current_user,
    ) -> TrainingAlertRule:
        self._permissions.require_operation(
            workspace_id=rule.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        updated = self._alert_rules.update(
            rule,
            name=name,
            operator=operator,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            is_active=is_active,
            channels=channels,
        )
        self._audit.record(
            event_type="training.alert_rule.updated",
            user_id=current_user.id if current_user else None,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": rule.workspace_id,
                "rule_id": rule.id,
                "changes": {
                    "name": name,
                    "operator": operator,
                    "threshold": threshold,
                    "cooldown_seconds": cooldown_seconds,
                    "is_active": is_active,
                },
            },
        )
        return updated

    # ------------------------------------------------------------------ #
    # Alert management
    # ------------------------------------------------------------------ #

    def list_alerts_for_workspace(self, workspace_id: int, limit: int = 50) -> Sequence[TrainingAlert]:
        return self._alerts.list_recent_for_workspace(workspace_id, limit=limit)

    def list_alerts_for_run(self, run_id: int) -> Sequence[TrainingAlert]:
        return self._alerts.list_for_run(run_id)

    def record_evaluation_alert(
        self,
        *,
        workspace_id: int,
        run_id: int,
        metric: str,
        value: float,
        threshold: float,
        triggered_at: datetime | None = None,
        notes: str | None = None,
    ) -> TrainingAlert | None:
        """Create or reuse an alert for automatic evaluation thresholds."""

        metric_mapping: dict[str, TrainingMetricName] = {
            "bleu": TrainingMetricName.EVALUATION_BLEU,
            "rouge_l": TrainingMetricName.EVALUATION_ROUGE_L,
            "exact_match": TrainingMetricName.EVALUATION_EXACT_MATCH,
            "perplexity": TrainingMetricName.EVALUATION_PERPLEXITY,
            "evaluation_failure": TrainingMetricName.EVALUATION_FAILURE,
        }
        mapped_metric = metric_mapping.get(metric.lower())
        if mapped_metric is None:
            return None

        operator = (
            TrainingAlertOperator.GREATER_THAN
            if mapped_metric in {TrainingMetricName.EVALUATION_PERPLEXITY, TrainingMetricName.EVALUATION_FAILURE}
            else TrainingAlertOperator.LESS_THAN
        )
        rule_name = f"[自动评估] {mapped_metric.value.replace('_', ' ').upper()}"
        rule = self._alert_rules.get_by_workspace_and_name(workspace_id, rule_name)
        cooldown_seconds = 900
        if rule is None:
            rule = self._alert_rules.create(
                workspace_id=workspace_id,
                name=rule_name,
                metric=mapped_metric,
                operator=operator,
                threshold=threshold,
                cooldown_seconds=cooldown_seconds,
                channels=None,
                created_by=None,
            )
        else:
            rule = self._alert_rules.update(
                rule,
                operator=operator,
                threshold=threshold,
                cooldown_seconds=cooldown_seconds,
            )

        event_time = triggered_at or datetime.utcnow()
        latest = self._alerts.get_latest_for_rule(rule.id, run_id)
        if latest and (event_time - latest.triggered_at) < timedelta(seconds=rule.cooldown_seconds):
            return latest

        alert = self._alerts.create(
            rule_id=rule.id,
            run_id=run_id,
            value=value,
            triggered_at=event_time,
        )
        if notes:
            self._alerts.update_status(
                alert,
                status=TrainingAlertStatus.TRIGGERED,
                actor_id=None,
                notes=notes,
            )
        self._audit.record(
            event_type="evaluation.alert.triggered",
            user_id=None,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace_id,
                "run_id": run_id,
                "metric": mapped_metric.value,
                "value": value,
                "threshold": threshold,
            },
        )
        return alert

    def update_alert_status(
        self,
        *,
        alert: TrainingAlert,
        status: TrainingAlertStatus,
        current_user,
        notes: str | None = None,
    ) -> TrainingAlert:
        self._permissions.require_operation(
            workspace_id=alert.rule.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        updated = self._alerts.update_status(
            alert,
            status=status,
            actor_id=current_user.id if current_user else None,
            notes=notes,
        )
        self._audit.record(
            event_type="training.alert.status_changed",
            user_id=current_user.id if current_user else None,
            ip_address=None,
            user_agent=None,
            payload={
                "alert_id": alert.id,
                "rule_id": alert.rule_id,
                "run_id": alert.run_id,
                "status": status,
                "notes": notes,
            },
        )
        return updated

    # ------------------------------------------------------------------ #
    # Export helpers
    # ------------------------------------------------------------------ #

    def export_metrics_csv(self, run_id: int) -> bytes:
        samples = self.list_metric_samples(run_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["run_id", "metric", "value", "recorded_at"])
        for sample in samples:
            writer.writerow([sample.run_id, sample.metric.value, sample.value, sample.recorded_at.isoformat()])
        return buffer.getvalue().encode("utf-8")

    def export_alerts_csv(self, workspace_id: int) -> bytes:
        alerts = self.list_alerts_for_workspace(workspace_id, limit=200)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["alert_id", "rule_id", "run_id", "status", "value", "triggered_at", "resolved_at"])
        for alert in alerts:
            writer.writerow(
                [
                    alert.id,
                    alert.rule_id,
                    alert.run_id,
                    alert.status.value,
                    alert.value,
                    alert.triggered_at.isoformat(),
                    alert.resolved_at.isoformat() if alert.resolved_at else "",
                ]
            )
        return buffer.getvalue().encode("utf-8")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _evaluate_rules(
        self,
        *,
        workspace_id: int,
        run: TrainingRun,
        metric: TrainingMetricName,
        value: float,
        triggered_at: datetime,
    ) -> None:
        rules = self._alert_rules.list_active_for_workspace(workspace_id)
        for rule in rules:
            if rule.metric != metric or not rule.is_active:
                continue
            if not self._should_trigger(rule.operator, value, rule.threshold):
                continue

            latest_alert = self._alerts.get_latest_for_rule(rule.id, run.id)
            if latest_alert and latest_alert.triggered_at and rule.cooldown_seconds:
                delta = triggered_at - latest_alert.triggered_at
                if delta < timedelta(seconds=rule.cooldown_seconds):
                    continue

            alert = self._alerts.create(
                rule_id=rule.id,
                run_id=run.id,
                value=value,
                triggered_at=triggered_at,
            )
            self._audit.record(
                event_type="training.alert.triggered",
                user_id=None,
                ip_address=None,
                user_agent=None,
                payload={
                    "alert_id": alert.id,
                    "rule_id": rule.id,
                    "run_id": run.id,
                    "metric": metric,
                    "value": value,
                    "threshold": rule.threshold,
                },
            )

    @staticmethod
    def _should_trigger(operator: TrainingAlertOperator, value: float, threshold: float) -> bool:
        if operator == TrainingAlertOperator.GREATER_THAN:
            return value > threshold
        if operator == TrainingAlertOperator.GREATER_OR_EQUAL:
            return value >= threshold
        if operator == TrainingAlertOperator.LESS_THAN:
            return value < threshold
        if operator == TrainingAlertOperator.LESS_OR_EQUAL:
            return value <= threshold
        return False

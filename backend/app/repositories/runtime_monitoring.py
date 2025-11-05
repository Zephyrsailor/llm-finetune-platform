"""Repositories for runtime monitoring alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlmodel import Session

from app.models import (
    RuntimeAlert,
    RuntimeAlertOperator,
    RuntimeAlertRule,
    RuntimeAlertStatus,
    RuntimeMetricName,
)


class RuntimeAlertRuleRepository:
    """Persist and query runtime alert rules."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(self, workspace_id: int) -> Sequence[RuntimeAlertRule]:
        statement = (
            select(RuntimeAlertRule)
            .where(RuntimeAlertRule.workspace_id == workspace_id)
            .order_by(RuntimeAlertRule.created_at.desc())
        )
        return tuple(self._normalize_rules(self._session.exec(statement).all()))

    def list_active_for_workspace(self, workspace_id: int) -> Sequence[RuntimeAlertRule]:
        statement = (
            select(RuntimeAlertRule)
            .where(
                RuntimeAlertRule.workspace_id == workspace_id,
                RuntimeAlertRule.is_active.is_(True),
            )
            .order_by(RuntimeAlertRule.created_at.desc())
        )
        return tuple(self._normalize_rules(self._session.exec(statement).all()))

    def list_for_deployment(self, deployment_id: int) -> Sequence[RuntimeAlertRule]:
        statement = (
            select(RuntimeAlertRule)
            .where(RuntimeAlertRule.deployment_id == deployment_id)
            .order_by(RuntimeAlertRule.created_at.desc())
        )
        return tuple(self._normalize_rules(self._session.exec(statement).all()))

    @staticmethod
    def _normalize_rules(result_items: list) -> list[RuntimeAlertRule]:
        normalized: list[RuntimeAlertRule] = []
        for item in result_items:
            if isinstance(item, RuntimeAlertRule):
                normalized.append(item)
            elif isinstance(item, tuple) and item:
                first = item[0]
                if isinstance(first, RuntimeAlertRule):
                    normalized.append(first)
            else:
                # SQLAlchemy Row object
                candidate = None
                try:
                    mapping = item._mapping  # type: ignore[attr-defined]
                    # Attempt lookup by mapped entity or table key
                    candidate = mapping.get(RuntimeAlertRule)
                    if candidate is None:
                        candidate = mapping.get("RuntimeAlertRule")
                    if candidate is None:
                        candidate = mapping.get("runtime_alert_rules")
                except AttributeError:
                    candidate = None
                if isinstance(candidate, RuntimeAlertRule):
                    normalized.append(candidate)
        return normalized

    def get(self, rule_id: int) -> RuntimeAlertRule | None:
        return self._session.get(RuntimeAlertRule, rule_id)

    def get_by_workspace_and_name(self, workspace_id: int, name: str) -> RuntimeAlertRule | None:
        statement = (
            select(RuntimeAlertRule)
            .where(
                RuntimeAlertRule.workspace_id == workspace_id,
                RuntimeAlertRule.name == name,
            )
            .order_by(RuntimeAlertRule.created_at.desc())
        )
        return self._session.exec(statement).first()

    def create(
        self,
        *,
        workspace_id: int,
        deployment_id: int | None,
        name: str,
        metric: RuntimeMetricName,
        operator: RuntimeAlertOperator,
        threshold: float,
        cooldown_seconds: int,
        channels: dict | None,
        created_by: int | None,
    ) -> RuntimeAlertRule:
        now = datetime.utcnow()
        rule = RuntimeAlertRule(
            workspace_id=workspace_id,
            deployment_id=deployment_id,
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
        rule: RuntimeAlertRule,
        *,
        name: str | None = None,
        operator: RuntimeAlertOperator | None = None,
        threshold: float | None = None,
        cooldown_seconds: int | None = None,
        is_active: bool | None = None,
        channels: dict | None = None,
        deployment_id: int | None = None,
    ) -> RuntimeAlertRule:
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
        if deployment_id is not None:
            rule.deployment_id = deployment_id
        rule.updated_at = datetime.utcnow()
        self._session.add(rule)
        self._session.flush()
        self._session.refresh(rule)
        return rule


class RuntimeAlertRepository:
    """Persist and query runtime alerts."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        rule_id: int,
        workspace_id: int,
        deployment_id: int | None,
        value: float,
        triggered_at: datetime | None = None,
        recommendation: str | None = None,
    ) -> RuntimeAlert:
        alert = RuntimeAlert(
            rule_id=rule_id,
            workspace_id=workspace_id,
            deployment_id=deployment_id,
            value=value,
            triggered_at=triggered_at or datetime.utcnow(),
            recommendation=recommendation,
            status=RuntimeAlertStatus.TRIGGERED,
        )
        self._session.add(alert)
        self._session.flush()
        self._session.refresh(alert)
        return alert

    def list_recent_for_workspace(self, workspace_id: int, limit: int = 100) -> Sequence[RuntimeAlert]:
        statement = (
            select(RuntimeAlert)
            .where(RuntimeAlert.workspace_id == workspace_id)
            .order_by(RuntimeAlert.triggered_at.desc())
            .limit(limit)
        )
        return tuple(self._normalize_alerts(self._session.exec(statement).all()))

    def list_for_deployment(self, deployment_id: int, limit: int = 100) -> Sequence[RuntimeAlert]:
        statement = (
            select(RuntimeAlert)
            .where(RuntimeAlert.deployment_id == deployment_id)
            .order_by(RuntimeAlert.triggered_at.desc())
            .limit(limit)
        )
        return tuple(self._normalize_alerts(self._session.exec(statement).all()))

    def get(self, alert_id: int) -> RuntimeAlert | None:
        return self._session.get(RuntimeAlert, alert_id)

    def get_latest_for_rule(
        self,
        rule_id: int,
        deployment_id: int | None,
    ) -> RuntimeAlert | None:
        statement = (
            select(RuntimeAlert)
            .where(RuntimeAlert.rule_id == rule_id)
            .order_by(RuntimeAlert.triggered_at.desc())
        )
        if deployment_id is not None:
            statement = statement.where(RuntimeAlert.deployment_id == deployment_id)
        row = self._session.exec(statement).first()
        if isinstance(row, RuntimeAlert):
            return row
        if row is None:
            return None
        if isinstance(row, tuple) and row:
            first = row[0]
            if isinstance(first, RuntimeAlert):
                return first
        try:
            mapping = row._mapping  # type: ignore[attr-defined]
        except AttributeError:
            return None
        candidate = mapping.get(RuntimeAlert) or mapping.get("RuntimeAlert") or mapping.get("runtime_alerts")
        return candidate if isinstance(candidate, RuntimeAlert) else None

    def update_status(
        self,
        alert: RuntimeAlert,
        *,
        status: RuntimeAlertStatus,
        actor_id: int | None,
        notes: str | None = None,
    ) -> RuntimeAlert:
        now = datetime.utcnow()
        alert.status = status
        if status == RuntimeAlertStatus.ACKNOWLEDGED:
            alert.acknowledged_by = actor_id
            alert.acknowledged_at = now
        if status == RuntimeAlertStatus.RESOLVED:
            alert.resolved_by = actor_id
            alert.resolved_at = now
        if notes is not None:
            alert.notes = notes
        alert.updated_at = now
        self._session.add(alert)
        self._session.flush()
        self._session.refresh(alert)
        return alert

    @staticmethod
    def _normalize_alerts(result_items: list) -> list[RuntimeAlert]:
        normalized: list[RuntimeAlert] = []
        for item in result_items:
            if isinstance(item, RuntimeAlert):
                normalized.append(item)
            elif isinstance(item, tuple) and item:
                first = item[0]
                if isinstance(first, RuntimeAlert):
                    normalized.append(first)
            else:
                try:
                    mapping = item._mapping  # type: ignore[attr-defined]
                except AttributeError:
                    mapping = None
                if mapping:
                    candidate = mapping.get(RuntimeAlert) or mapping.get("RuntimeAlert") or mapping.get("runtime_alerts")
                    if isinstance(candidate, RuntimeAlert):
                        normalized.append(candidate)
        return normalized

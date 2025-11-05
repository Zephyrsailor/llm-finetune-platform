"""Runtime monitoring aggregations and alert orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlmodel import Session

from app.models import (
    InferenceCallStatus,
    RuntimeAlert,
    RuntimeAlertOperator,
    RuntimeAlertRule,
    RuntimeAlertStatus,
    RuntimeMetricName,
    UsageWindowScope,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment import DeploymentRepository
from app.repositories.inference import InferenceCallRepository, InferenceUsageRepository
from app.repositories.runtime_monitoring import (
    RuntimeAlertRepository,
    RuntimeAlertRuleRepository,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation

_RECOMMENDATIONS: dict[RuntimeMetricName, str] = {
    RuntimeMetricName.LATENCY_P95_MS: "建议扩容推理实例或调整模型配置以降低延迟。",
    RuntimeMetricName.ERROR_RATE: "建议立即回滚到上一稳定版本并排查错误日志。",
    RuntimeMetricName.QPS: "建议增加实例数量或提升配额阈值以缓解流量压力。",
    RuntimeMetricName.TOKEN_THROUGHPUT_PER_MINUTE: "建议优化请求批量或申请更高配额。",
    RuntimeMetricName.GPU_MEMORY_MB: "建议检查模型加载与缓存策略，释放显存或重启实例。",
    RuntimeMetricName.GPU_UTILIZATION: "建议开启自动扩缩容或调整实例规格。",
}


class RuntimeMonitoringService:
    """Provide runtime monitoring aggregations and alert orchestration."""

    def __init__(self, session: Session):
        self._session = session
        self._deployments = DeploymentRepository(session)
        self._inference_calls = InferenceCallRepository(session)
        self._inference_usage = InferenceUsageRepository(session)
        self._alert_rules = RuntimeAlertRuleRepository(session)
        self._alerts = RuntimeAlertRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_overview(
        self,
        *,
        workspace_id: int,
        current_user: User,
        window_minutes: int = 15,
        deployment_id: int | None = None,
    ) -> dict[str, Any]:
        """Return aggregated metrics, resources and latest alerts."""
        self._require_manage(workspace_id, current_user)
        window_minutes = max(1, min(window_minutes, 1440))
        aggregate_metrics, per_deployment_metrics, resource_usage = self._collect_metrics(
            workspace_id=workspace_id,
            window_minutes=window_minutes,
            deployment_id=deployment_id,
        )
        self._evaluate_alert_rules(
            workspace_id=workspace_id,
            aggregate_metrics=aggregate_metrics,
            per_deployment_metrics=per_deployment_metrics,
        )
        alerts = self._alerts.list_recent_for_workspace(workspace_id)
        aggregate_payload = self._sanitize_metric_payload(aggregate_metrics)
        per_deployment_payloads = [
            self._sanitize_metric_payload(self._merge_metric_payload(item, resource_usage))
            for item in per_deployment_metrics.values()
        ]
        return {
            "window_minutes": window_minutes,
            "metrics": aggregate_payload,
            "per_deployment": per_deployment_payloads,
            "alerts": [self._serialize_alert(alert) for alert in alerts],
            "resource_usage": resource_usage,
        }

    def list_alert_rules(
        self,
        *,
        workspace_id: int,
        current_user: User,
    ) -> list[dict[str, Any]]:
        """Return alert rules scoped to workspace."""
        self._require_manage(workspace_id, current_user)
        rules = self._alert_rules.list_for_workspace(workspace_id)
        return [self._serialize_rule(rule) for rule in rules]

    def create_alert_rule(
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
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        """Create a new alert threshold rule."""
        self._require_manage(workspace_id, current_user)
        rule = self._alert_rules.create(
            workspace_id=workspace_id,
            deployment_id=deployment_id,
            name=name,
            metric=metric,
            operator=operator,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            channels=channels,
            created_by=current_user.id if current_user else None,
        )
        self._audits.record(
            event_type="runtime.alert_rule.created",
            user_id=current_user.id if current_user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "deployment_id": deployment_id,
                "rule_id": rule.id,
                "metric": metric.value,
                "threshold": threshold,
            },
        )
        return self._serialize_rule(rule)

    def update_alert_rule(
        self,
        *,
        rule: RuntimeAlertRule,
        name: str | None,
        operator: RuntimeAlertOperator | None,
        threshold: float | None,
        cooldown_seconds: int | None,
        is_active: bool | None,
        channels: dict | None,
        deployment_id: int | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        """Update threshold rule configuration."""
        self._require_manage(rule.workspace_id, current_user)
        updated = self._alert_rules.update(
            rule,
            name=name,
            operator=operator,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            is_active=is_active,
            channels=channels,
            deployment_id=deployment_id,
        )
        self._audits.record(
            event_type="runtime.alert_rule.updated",
            user_id=current_user.id if current_user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": updated.workspace_id,
                "rule_id": updated.id,
                "changes": {
                    "name": name,
                    "operator": operator.value if operator else None,
                    "threshold": threshold,
                    "cooldown_seconds": cooldown_seconds,
                    "is_active": is_active,
                    "deployment_id": deployment_id,
                },
            },
        )
        return self._serialize_rule(updated)

    def list_alerts(
        self,
        *,
        workspace_id: int,
        current_user: User,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent alerts for workspace."""
        self._require_manage(workspace_id, current_user)
        alerts = self._alerts.list_recent_for_workspace(workspace_id, limit=limit)
        return [self._serialize_alert(alert) for alert in alerts]

    def update_alert_status(
        self,
        *,
        alert: RuntimeAlert,
        status: RuntimeAlertStatus,
        notes: str | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        """Acknowledge or resolve an alert."""
        self._require_manage(alert.workspace_id, current_user)
        updated = self._alerts.update_status(
            alert,
            status=status,
            actor_id=current_user.id if current_user else None,
            notes=notes,
        )
        self._audits.record(
            event_type="runtime.alert.status_changed",
            user_id=current_user.id if current_user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": updated.workspace_id,
                "alert_id": updated.id,
                "rule_id": updated.rule_id,
                "status": status.value,
                "notes": notes,
            },
        )
        return self._serialize_alert(updated)

    def get_rule(self, rule_id: int) -> RuntimeAlertRule | None:
        """Lookup alert rule by identifier."""
        return self._alert_rules.get(rule_id)

    def get_alert(self, alert_id: int) -> RuntimeAlert | None:
        """Lookup alert by identifier."""
        return self._alerts.get(alert_id)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _collect_metrics(
        self,
        *,
        workspace_id: int,
        window_minutes: int,
        deployment_id: int | None,
    ) -> tuple[dict[str, Any], dict[int, dict[str, Any]], list[dict[str, Any]]]:
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        calls = self._inference_calls.list_since(
            workspace_id=workspace_id,
            since=window_start,
            deployment_id=deployment_id,
        )
        window_seconds = window_minutes * 60

        per_deployment: dict[int, dict[str, Any]] = {}
        aggregate = {
            "total_calls": 0,
            "success_count": 0,
            "rate_limited_count": 0,
            "error_count": 0,
            "latency_p95_ms": None,
            "qps": 0.0,
            "error_rate": 0.0,
            "token_throughput_per_minute": 0.0,
            "token_throughput_per_second": 0.0,
            "total_tokens": 0,
            "latency_samples": [],
            "daily_usage": self._summarize_daily_usage(workspace_id),
        }

        def ensure_deployment_metrics(deployment_id_value: int | None) -> dict[str, Any]:
            identifier = deployment_id_value or 0
            metrics = per_deployment.get(identifier)
            if metrics is None:
                metrics = {
                    "deployment_id": deployment_id_value,
                    "total_calls": 0,
                    "success_count": 0,
                    "rate_limited_count": 0,
                    "error_count": 0,
                    "latency_samples": [],
                    "latency_p95_ms": None,
                    "qps": 0.0,
                    "error_rate": 0.0,
                    "token_throughput_per_minute": 0.0,
                    "token_throughput_per_second": 0.0,
                    "total_tokens": 0,
                }
                per_deployment[identifier] = metrics
            return metrics

        for call in calls:
            target_metrics = ensure_deployment_metrics(call.deployment_id or 0)
            aggregate["total_calls"] += 1
            target_metrics["total_calls"] += 1

            if call.status == InferenceCallStatus.SUCCESS:
                aggregate["success_count"] += 1
                target_metrics["success_count"] += 1
            elif call.status == InferenceCallStatus.RATE_LIMITED:
                aggregate["rate_limited_count"] += 1
                target_metrics["rate_limited_count"] += 1
                aggregate["error_count"] += 1
                target_metrics["error_count"] += 1
            else:
                aggregate["error_count"] += 1
                target_metrics["error_count"] += 1

            if call.latency_ms is not None:
                aggregate["latency_samples"].append(call.latency_ms)
                target_metrics["latency_samples"].append(call.latency_ms)

            total_tokens = (call.input_tokens or 0) + (call.output_tokens or 0)
            aggregate["total_tokens"] += total_tokens
            target_metrics["total_tokens"] += total_tokens

        for metrics in per_deployment.values():
            metrics["latency_p95_ms"] = self._percentile(metrics["latency_samples"], 95)
            metrics["qps"] = self._rate(metrics["total_calls"], window_seconds)
            metrics["error_rate"] = self._ratio(metrics["error_count"], metrics["total_calls"])
            metrics["token_throughput_per_second"] = self._rate(metrics["total_tokens"], window_seconds)
            metrics["token_throughput_per_minute"] = metrics["token_throughput_per_second"] * 60

        aggregate["latency_p95_ms"] = self._percentile(aggregate["latency_samples"], 95)
        aggregate["qps"] = self._rate(aggregate["total_calls"], window_seconds)
        aggregate["error_rate"] = self._ratio(aggregate["error_count"], aggregate["total_calls"])
        aggregate["token_throughput_per_second"] = self._rate(aggregate["total_tokens"], window_seconds)
        aggregate["token_throughput_per_minute"] = aggregate["token_throughput_per_second"] * 60

        deployments = self._deployments.list_for_workspace(workspace_id=workspace_id)
        if deployment_id is not None:
            deployments = tuple(item for item in deployments if item.id == deployment_id)

        for deployment in deployments:
            ensure_deployment_metrics(deployment.id)

        resource_usage: list[dict[str, Any]] = []
        for deployment in deployments:
            metrics_payload = {
                "deployment_id": deployment.id,
                "environment": deployment.environment,
                "status": deployment.status.value,
                "traffic_percent": deployment.traffic_percent,
                "metrics": dict(deployment.metrics_json or {}),
                "updated_at": deployment.updated_at.isoformat(),
            }
            # Fill derived values for existing per-deployment metrics
            derived = per_deployment.get(deployment.id or 0)
            if derived:
                metrics_payload["qps"] = derived["qps"]
                metrics_payload["error_rate"] = derived["error_rate"]
                metrics_payload["latency_p95_ms"] = derived["latency_p95_ms"]
                metrics_payload["token_throughput_per_minute"] = derived["token_throughput_per_minute"]
                derived["metrics"] = metrics_payload["metrics"]
            resource_usage.append(metrics_payload)

        aggregate["gpu_memory_mb"] = self._average_resource_metric(resource_usage, "gpu_memory_mb")
        aggregate["gpu_utilization"] = self._average_resource_metric(resource_usage, "gpu_utilization")

        return aggregate, per_deployment, resource_usage

    def _summarize_daily_usage(self, workspace_id: int) -> dict[str, int]:
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        entries = self._inference_usage.list_for_workspace(
            workspace_id=workspace_id,
            scope=UsageWindowScope.DAY,
            since=day_start,
        )
        total_requests = sum(item.request_count for item in entries)
        total_tokens = sum(item.token_count for item in entries)
        return {
            "requests": total_requests,
            "tokens": total_tokens,
        }

    def _evaluate_alert_rules(
        self,
        *,
        workspace_id: int,
        aggregate_metrics: dict[str, Any],
        per_deployment_metrics: dict[int, dict[str, Any]],
    ) -> None:
        rules = self._alert_rules.list_active_for_workspace(workspace_id)
        now = datetime.utcnow()
        for rule in rules:
            if rule.deployment_id:
                metrics_source = per_deployment_metrics.get(rule.deployment_id)
            else:
                metrics_source = aggregate_metrics
            if not metrics_source:
                continue
            value = self._resolve_metric_value(rule.metric, metrics_source, aggregate_metrics)
            if value is None:
                continue
            if not self._should_trigger(rule.operator, value, rule.threshold):
                continue
            latest = self._alerts.get_latest_for_rule(rule.id, rule.deployment_id)
            if latest and rule.cooldown_seconds:
                delta = now - latest.triggered_at
                if delta.total_seconds() < rule.cooldown_seconds and latest.status == RuntimeAlertStatus.TRIGGERED:
                    continue
            recommendation = _RECOMMENDATIONS.get(rule.metric)
            self._alerts.create(
                rule_id=rule.id,
                workspace_id=workspace_id,
                deployment_id=rule.deployment_id,
                value=value,
                triggered_at=now,
                recommendation=recommendation,
            )
            self._audits.record(
                event_type="runtime.alert.triggered",
                user_id=None,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": workspace_id,
                    "deployment_id": rule.deployment_id,
                    "rule_id": rule.id,
                    "metric": rule.metric.value,
                    "value": value,
                    "threshold": rule.threshold,
                },
            )

    @staticmethod
    def _resolve_metric_value(
        metric: RuntimeMetricName,
        metrics_source: dict[str, Any],
        aggregate_metrics: dict[str, Any],
    ) -> float | None:
        mapping = {
            RuntimeMetricName.QPS: metrics_source.get("qps"),
            RuntimeMetricName.LATENCY_P95_MS: metrics_source.get("latency_p95_ms"),
            RuntimeMetricName.ERROR_RATE: metrics_source.get("error_rate"),
            RuntimeMetricName.TOKEN_THROUGHPUT_PER_MINUTE: metrics_source.get("token_throughput_per_minute"),
            RuntimeMetricName.GPU_MEMORY_MB: RuntimeMonitoringService._infer_resource_value(
                metrics_source,
                aggregate_metrics,
                key="gpu_memory_mb",
            ),
            RuntimeMetricName.GPU_UTILIZATION: RuntimeMonitoringService._infer_resource_value(
                metrics_source,
                aggregate_metrics,
                key="gpu_utilization",
            ),
        }
        value = mapping.get(metric)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _infer_resource_value(
        metrics_source: dict[str, Any],
        aggregate_metrics: dict[str, Any],
        *,
        key: str,
    ) -> float | None:
        # Primary source: metrics dict present in resource usage merge
        metrics_dict = metrics_source.get("metrics")
        if isinstance(metrics_dict, dict):
            value = metrics_dict.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        # Fallback to aggregate metrics reference if available
        fallback = aggregate_metrics.get(key)
        if isinstance(fallback, (int, float)):
            return float(fallback)
        return None

    def _require_manage(self, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.DEPLOYMENT_MANAGE,
            ip_address=None,
            user_agent=None,
        )

    @staticmethod
    def _percentile(values: Iterable[float], percentile: float) -> float | None:
        sequence = sorted(values)
        if not sequence:
            return None
        if len(sequence) == 1:
            return float(sequence[0])
        rank = percentile / 100 * (len(sequence) - 1)
        lower_index = int(rank)
        upper_index = min(lower_index + 1, len(sequence) - 1)
        weight = rank - lower_index
        lower = float(sequence[lower_index])
        upper = float(sequence[upper_index])
        return lower * (1 - weight) + upper * weight

    @staticmethod
    def _rate(count: int, window_seconds: int) -> float:
        if window_seconds <= 0:
            return 0.0
        return float(count) / float(window_seconds)

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return float(numerator) / float(denominator)

    @staticmethod
    def _should_trigger(operator: RuntimeAlertOperator, value: float, threshold: float) -> bool:
        if operator == RuntimeAlertOperator.GREATER_THAN:
            return value > threshold
        if operator == RuntimeAlertOperator.GREATER_OR_EQUAL:
            return value >= threshold
        if operator == RuntimeAlertOperator.LESS_THAN:
            return value < threshold
        if operator == RuntimeAlertOperator.LESS_OR_EQUAL:
            return value <= threshold
        return False

    @staticmethod
    def _serialize_rule(rule: RuntimeAlertRule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "workspace_id": rule.workspace_id,
            "deployment_id": rule.deployment_id,
            "name": rule.name,
            "metric": rule.metric.value,
            "operator": rule.operator.value,
            "threshold": rule.threshold,
            "cooldown_seconds": rule.cooldown_seconds,
            "is_active": rule.is_active,
            "channels": rule.channels_json or {},
            "created_at": rule.created_at.isoformat(),
            "updated_at": rule.updated_at.isoformat(),
        }

    @staticmethod
    def _serialize_alert(alert: RuntimeAlert) -> dict[str, Any]:
        return {
            "id": alert.id,
            "workspace_id": alert.workspace_id,
            "deployment_id": alert.deployment_id,
            "rule_id": alert.rule_id,
            "value": alert.value,
            "status": alert.status.value,
            "triggered_at": alert.triggered_at.isoformat(),
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_by": alert.resolved_by,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "notes": alert.notes,
            "recommendation": alert.recommendation,
            "created_at": alert.created_at.isoformat(),
            "updated_at": alert.updated_at.isoformat(),
        }

    @staticmethod
    def _merge_metric_payload(
        deployment_metrics: dict[str, Any],
        resource_usage: list[dict[str, Any]],
    ) -> dict[str, Any]:
        deployment_id = deployment_metrics.get("deployment_id")
        resource = next(
            (item for item in resource_usage if item.get("deployment_id") == deployment_id),
            None,
        )
        payload = dict(deployment_metrics)
        if resource:
            payload["metrics"] = resource.get("metrics", {})
            payload["environment"] = resource.get("environment")
            payload["status"] = resource.get("status")
            payload["traffic_percent"] = resource.get("traffic_percent")
        return payload

    @staticmethod
    def _sanitize_metric_payload(metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in metrics.items()
            if key not in {"latency_samples", "total_tokens"}
        }

    @staticmethod
    def _average_resource_metric(resources: list[dict[str, Any]], key: str) -> float | None:
        values: list[float] = []
        for item in resources:
            metrics = item.get("metrics")
            if isinstance(metrics, dict):
                value = metrics.get(key)
                if isinstance(value, (int, float)):
                    values.append(float(value))
        if not values:
            return None
        return sum(values) / len(values)

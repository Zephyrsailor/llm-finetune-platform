"""Deployment orchestration service."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    Deployment,
    DeploymentEvent,
    DeploymentStatus,
    ModelVersion,
    ModelVersionStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment import (
    DeploymentRepository,
    DeploymentEventRepository,
    DeploymentInstanceRepository,
)
from app.repositories.model_registry import ModelVersionRepository
from app.repositories.workspace import WorkspaceRepository, ProjectRepository
from app.services.errors import (
    AccessDeniedError,
    ModelRegistryError,
    ModelVersionPromotionError,
    WorkspaceNotFoundError,
    ProjectNotFoundError,
)
from app.services.model_registry import ModelRegistryService
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


class DeploymentService:
    """High-level orchestration for deployment lifecycle."""

    def __init__(self, session: Session):
        self._session = session
        self._deployments = DeploymentRepository(session)
        self._events = DeploymentEventRepository(session)
        self._instances = DeploymentInstanceRepository(session)
        self._versions = ModelVersionRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._projects = ProjectRepository(session)
        self._audits = AuditLogRepository(session)
        self._permissions = PermissionService(session)
        self._registry = ModelRegistryService(session)

    @contextmanager
    def _transaction(self):
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def list_deployments(
        self,
        *,
        workspace_id: int,
        current_user,
        project_id: int | None = None,
        status: DeploymentStatus | None = None,
    ) -> list[dict[str, Any]]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_view(workspace.id, current_user)
        items = self._deployments.list_for_workspace(
            workspace_id=workspace.id,
            project_id=project_id,
            status=status,
        )
        return [self._serialize(deployment) for deployment in items]

    def get_deployment(self, deployment_id: int, *, current_user) -> dict[str, Any]:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise ModelRegistryError("部署记录不存在。")
        self._require_view(deployment.workspace_id, current_user)
        return self._serialize(deployment)

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def create_deployment(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        model_version_id: int,
        environment: str,
        config: dict | None,
        notes: str | None,
        current_user,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        workspace = self._ensure_workspace(workspace_id)
        project = self._ensure_project(workspace.id, project_id) if project_id is not None else None
        self._require_manage(workspace.id, current_user, ip_address=ip_address, user_agent=user_agent)

        version = self._versions.get(model_version_id)
        if version is None:
            raise ModelRegistryError("模型版本不存在。")

        # Validate ownership
        model = version.model
        if model.workspace_id != workspace.id:
            raise ModelRegistryError("模型版本不属于目标工作空间。")

        if version.status != ModelVersionStatus.PRODUCTION:
            raise ModelVersionPromotionError("仅允许对生产状态模型版本进行部署。")

        self._ensure_evaluation_gate(version)

        with self._transaction():
            deployment = self._deployments.create(
                workspace_id=workspace.id,
                project_id=project.id if project else None,
                model_version_id=version.id,
                environment=environment,
                status=DeploymentStatus.PENDING,
                config=config,
                metrics=None,
                notes=notes,
                created_by=current_user.id,
            )
            self._events.create(
                deployment_id=deployment.id,
                event_type="deployment.requested",
                level="INFO",
                message=f"请求部署模型版本 #{version.id} 到环境 {environment}",
                payload={
                    "model_version_id": version.id,
                    "environment": environment,
                },
            )
            self._instances.create(
                deployment_id=deployment.id,
                environment=environment,
                status=DeploymentStatus.PENDING,
                config=config,
                metrics=None,
                endpoint_url=None,
                access_token=None,
                traffic_percent=None,
                health_checked_at=None,
            )
        self._session.commit()

        self._audits.record(
            event_type="model.version.deploy_requested",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace.id,
                "project_id": project.id if project else None,
                "model_version_id": version.id,
                "deployment_id": deployment.id,
            },
        )

        from app.tasks.deployment import run_deployment_job

        run_deployment_job.delay(deployment.id)
        return self._serialize(deployment)

    def update_traffic(
        self,
        *,
        deployment_id: int,
        traffic_percent: float,
        current_user,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise ModelRegistryError("部署记录不存在。")
        self._require_manage(deployment.workspace_id, current_user, ip_address=ip_address, user_agent=user_agent)
        if not (0 <= traffic_percent <= 100):
            raise ModelRegistryError("流量占比必须介于 0 到 100 之间。")

        with self._transaction():
            updated = self._deployments.update(
                deployment,
                traffic_percent=traffic_percent,
                updated_by=current_user.id,
            )
            instance = self._instances.get_latest(deployment.id)
            if instance is None:
                self._instances.create(
                    deployment_id=deployment.id,
                    environment=deployment.environment,
                    status=deployment.status,
                    config=deployment.config_json,
                    metrics=deployment.metrics_json,
                    endpoint_url=deployment.endpoint_url,
                    access_token=deployment.access_token,
                    traffic_percent=traffic_percent,
                    health_checked_at=None,
                )
            else:
                self._instances.update(
                    instance,
                    traffic_percent=traffic_percent,
                )
            self._events.create(
                deployment_id=deployment.id,
                event_type="deployment.traffic_adjusted",
                level="INFO",
                message=f"更新流量占比为 {traffic_percent}%",
                payload={"traffic_percent": traffic_percent},
            )
        self._session.commit()
        return self._serialize(updated)

    def rollback(
        self,
        *,
        deployment_id: int,
        reason: str | None,
        current_user,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise ModelRegistryError("部署记录不存在。")
        self._require_manage(deployment.workspace_id, current_user, ip_address=ip_address, user_agent=user_agent)

        from app.tasks.deployment import run_deployment_rollback

        run_deployment_rollback.delay(deployment.id, reason or "manual rollback")
        return self._serialize(deployment)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_workspace(self, workspace_id: int):
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在。")
        return workspace

    def _ensure_project(self, workspace_id: int, project_id: int):
        project = self._projects.get(project_id)
        if project is None or project.workspace_id != workspace_id:
            raise ProjectNotFoundError("项目不存在或不属于指定工作空间。")
        return project

    def _require_view(self, workspace_id: int, user):
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.EVALUATION_VIEW,
            ip_address=None,
            user_agent=None,
        )

    def _require_manage(self, workspace_id: int, user, *, ip_address: str | None, user_agent: str | None):
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.DEPLOYMENT_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _ensure_evaluation_gate(self, version: ModelVersion) -> None:
        metrics = version.evaluation_metrics_json or {}
        thresholds = metrics.get("thresholds") if isinstance(metrics, dict) else None
        if thresholds and any(info.get("triggered") for info in thresholds.values() if isinstance(info, dict)):
            raise ModelVersionPromotionError("评估指标未全部达标，禁止部署。")

    def _serialize(self, deployment: Deployment) -> dict[str, Any]:
        events = self._events.list_for_deployment(deployment.id)
        instances = self._instances.list_for_deployment(deployment.id)
        return {
            "id": deployment.id,
            "workspace_id": deployment.workspace_id,
            "project_id": deployment.project_id,
            "model_version_id": deployment.model_version_id,
            "environment": deployment.environment,
            "status": deployment.status.value,
            "endpoint_url": deployment.endpoint_url,
            "access_token": deployment.access_token,
            "config": deployment.config_json or {},
            "metrics": deployment.metrics_json or {},
            "traffic_percent": deployment.traffic_percent,
            "notes": deployment.notes,
            "created_at": deployment.created_at.isoformat(),
            "updated_at": deployment.updated_at.isoformat(),
            "events": [self._serialize_event(event) for event in events],
            "instances": [self._serialize_instance(instance) for instance in instances],
        }

    @staticmethod
    def _serialize_event(event: DeploymentEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "deployment_id": event.deployment_id,
            "event_type": event.event_type,
            "level": event.level,
            "message": event.message,
            "payload": event.payload_json or {},
            "created_at": event.created_at.isoformat(),
        }

    @staticmethod
    def _serialize_instance(instance) -> dict[str, Any]:
        return {
            "id": instance.id,
            "deployment_id": instance.deployment_id,
            "environment": instance.environment,
            "status": instance.status.value,
            "endpoint_url": instance.endpoint_url,
            "access_token": instance.access_token,
            "config": instance.config_json or {},
            "metrics": instance.metrics_json or {},
            "traffic_percent": instance.traffic_percent,
            "health_checked_at": instance.health_checked_at.isoformat() if instance.health_checked_at else None,
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat(),
        }

    # Utility functions used by Celery tasks
    def mark_deployment_status(
        self,
        deployment_id: int,
        *,
        status: DeploymentStatus,
        endpoint_url: str | None = None,
        access_token: str | None = None,
        metrics: dict | None = None,
        event_type: str,
        message: str,
        payload: dict | None,
    ) -> None:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return
        with self._transaction():
            updated = self._deployments.update(
                deployment,
                status=status,
                endpoint_url=endpoint_url,
                access_token=access_token,
                metrics=metrics,
            )
            instance = self._instances.get_latest(deployment.id)
            health_checked_at = datetime.utcnow() if metrics is not None else None
            if instance is None:
                self._instances.create(
                    deployment_id=deployment.id,
                    environment=updated.environment,
                    status=status,
                    config=updated.config_json,
                    metrics=metrics or updated.metrics_json,
                    endpoint_url=endpoint_url or updated.endpoint_url,
                    access_token=access_token or updated.access_token,
                    traffic_percent=updated.traffic_percent,
                    health_checked_at=health_checked_at,
                )
            else:
                self._instances.update(
                    instance,
                    status=status,
                    config=updated.config_json,
                    metrics=metrics or updated.metrics_json,
                    endpoint_url=endpoint_url or updated.endpoint_url,
                    access_token=access_token or updated.access_token,
                    traffic_percent=updated.traffic_percent,
                    health_checked_at=health_checked_at,
                )
            self._events.create(
                deployment_id=deployment.id,
                event_type=event_type,
                level="INFO" if status in (DeploymentStatus.ACTIVE, DeploymentStatus.DEPLOYING) else "ERROR",
                message=message,
                payload=payload,
            )
        self._session.commit()

    def record_event(
        self,
        deployment_id: int,
        *,
        event_type: str,
        level: str,
        message: str,
        payload: dict | None,
    ) -> None:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return
        with self._transaction():
            self._events.create(
                deployment_id=deployment.id,
                event_type=event_type,
                level=level,
                message=message,
                payload=payload,
            )
        self._session.commit()

    def finalize_success(
        self,
        deployment_id: int,
        *,
        endpoint_url: str,
        access_token: str,
        metrics: dict,
    ) -> None:
        self.mark_deployment_status(
            deployment_id,
            status=DeploymentStatus.ACTIVE,
            endpoint_url=endpoint_url,
            access_token=access_token,
            metrics=metrics,
            event_type="deployment.completed",
            message="部署成功并通过健康检查。",
            payload={"endpoint_url": endpoint_url},
        )

    def finalize_failure(
        self,
        deployment_id: int,
        *,
        message: str,
        payload: dict | None,
    ) -> None:
        self.mark_deployment_status(
            deployment_id,
            status=DeploymentStatus.FAILED,
            event_type="deployment.failed",
            message=message,
            payload=payload,
        )

    def mark_rolled_back(
        self,
        deployment_id: int,
        *,
        reason: str,
    ) -> None:
        self.mark_deployment_status(
            deployment_id,
            status=DeploymentStatus.ROLLED_BACK,
            event_type="deployment.rolled_back",
            message=f"已回滚部署：{reason}",
            payload={"reason": reason},
        )

    @staticmethod
    def generate_access_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def build_endpoint(model_version_id: int, environment: str) -> str:
        base = Path(settings.workspace_storage_root).absolute()
        return f"http://localhost:9000/{environment}/models/{model_version_id}"

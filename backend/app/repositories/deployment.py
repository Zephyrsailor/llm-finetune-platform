"""Repositories for deployment entities."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import Deployment, DeploymentEvent, DeploymentInstance, DeploymentStatus


class DeploymentRepository:
    """Persist and query deployment instances."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, deployment_id: int) -> Deployment | None:
        return self._session.get(Deployment, deployment_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: int,
        project_id: int | None = None,
        status: DeploymentStatus | None = None,
    ) -> Sequence[Deployment]:
        statement = select(Deployment).where(Deployment.workspace_id == workspace_id)
        if project_id is not None:
            statement = statement.where(Deployment.project_id == project_id)
        if status is not None:
            statement = statement.where(Deployment.status == status)
        statement = statement.order_by(Deployment.updated_at.desc())
        result = self._session.exec(statement)
        return tuple(result.all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        model_version_id: int,
        environment: str,
        status: DeploymentStatus,
        config: dict | None,
        metrics: dict | None,
        notes: str | None,
        created_by: int | None,
    ) -> Deployment:
        now = datetime.utcnow()
        deployment = Deployment(
            workspace_id=workspace_id,
            project_id=project_id,
            model_version_id=model_version_id,
            environment=environment,
            status=status,
            config_json=config,
            metrics_json=metrics,
            notes=notes,
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(deployment)
        self._session.flush()
        self._session.refresh(deployment)
        return deployment

    def get_active_for_model_version(self, model_version_id: int) -> Deployment | None:
        statement = select(Deployment).where(
            Deployment.model_version_id == model_version_id,
            Deployment.status == DeploymentStatus.ACTIVE,
        ).order_by(Deployment.updated_at.desc()).limit(1)
        return self._session.exec(statement).first()

    def update(
        self,
        deployment: Deployment,
        *,
        status: DeploymentStatus | None = None,
        endpoint_url: str | None = None,
        access_token: str | None = None,
        config: dict | None = None,
        metrics: dict | None = None,
        traffic_percent: float | None = None,
        notes: str | None = None,
        updated_by: int | None = None,
    ) -> Deployment:
        if status is not None:
            deployment.status = status
        if endpoint_url is not None:
            deployment.endpoint_url = endpoint_url
        if access_token is not None:
            deployment.access_token = access_token
        if config is not None:
            deployment.config_json = config
        if metrics is not None:
            deployment.metrics_json = metrics
        if traffic_percent is not None:
            deployment.traffic_percent = traffic_percent
        if notes is not None:
            deployment.notes = notes
        if updated_by is not None:
            deployment.updated_by = updated_by
        deployment.updated_at = datetime.utcnow()
        self._session.add(deployment)
        self._session.flush()
        self._session.refresh(deployment)
        return deployment


class DeploymentEventRepository:
    """Persist deployment event logs."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        deployment_id: int,
        event_type: str,
        level: str,
        message: str,
        payload: dict | None,
    ) -> DeploymentEvent:
        entry = DeploymentEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            level=level,
            message=message,
            payload_json=payload,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def list_for_deployment(self, deployment_id: int) -> Sequence[DeploymentEvent]:
        statement = (
            select(DeploymentEvent)
            .where(DeploymentEvent.deployment_id == deployment_id)
            .order_by(DeploymentEvent.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())


class DeploymentInstanceRepository:
    """Persist deployment runtime instances."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        deployment_id: int,
        environment: str,
        status: DeploymentStatus,
        config: dict | None,
        metrics: dict | None,
        endpoint_url: str | None,
        access_token: str | None,
        traffic_percent: float | None,
        health_checked_at: datetime | None,
    ) -> DeploymentInstance:
        now = datetime.utcnow()
        instance = DeploymentInstance(
            deployment_id=deployment_id,
            environment=environment,
            status=status,
            config_json=config,
            metrics_json=metrics,
            endpoint_url=endpoint_url,
            access_token=access_token,
            traffic_percent=traffic_percent,
            health_checked_at=health_checked_at,
            created_at=now,
            updated_at=now,
        )
        self._session.add(instance)
        self._session.flush()
        self._session.refresh(instance)
        return instance

    def list_for_deployment(self, deployment_id: int) -> Sequence[DeploymentInstance]:
        statement = (
            select(DeploymentInstance)
            .where(DeploymentInstance.deployment_id == deployment_id)
            .order_by(DeploymentInstance.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get_latest(self, deployment_id: int) -> DeploymentInstance | None:
        statement = (
            select(DeploymentInstance)
            .where(DeploymentInstance.deployment_id == deployment_id)
            .order_by(DeploymentInstance.created_at.desc())
            .limit(1)
        )
        return self._session.exec(statement).first()

    def update(
        self,
        instance: DeploymentInstance,
        *,
        status: DeploymentStatus | None = None,
        endpoint_url: str | None = None,
        access_token: str | None = None,
        config: dict | None = None,
        metrics: dict | None = None,
        traffic_percent: float | None = None,
        health_checked_at: datetime | None = None,
    ) -> DeploymentInstance:
        if status is not None:
            instance.status = status
        if endpoint_url is not None:
            instance.endpoint_url = endpoint_url
        if access_token is not None:
            instance.access_token = access_token
        if config is not None:
            instance.config_json = config
        if metrics is not None:
            instance.metrics_json = metrics
        if traffic_percent is not None:
            instance.traffic_percent = traffic_percent
        if health_checked_at is not None:
            instance.health_checked_at = health_checked_at
        instance.updated_at = datetime.utcnow()
        self._session.add(instance)
        self._session.flush()
        self._session.refresh(instance)
        return instance

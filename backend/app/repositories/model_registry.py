"""Repositories for registered models and versions."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlmodel import Session, select

from app.models import RegisteredModel, ModelVersion, ModelVersionStatus


class RegisteredModelRepository:
    """Persist and query registered models."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, model_id: int) -> RegisteredModel | None:
        return self._session.get(RegisteredModel, model_id)

    def get_by_name(self, *, workspace_id: int, name: str) -> RegisteredModel | None:
        statement = (
            select(RegisteredModel)
            .where(RegisteredModel.workspace_id == workspace_id)
            .where(RegisteredModel.name == name)
        )
        return self._session.exec(statement).first()

    def list_for_workspace(
        self,
        *,
        workspace_id: int,
        project_id: int | None = None,
    ) -> Sequence[RegisteredModel]:
        statement = select(RegisteredModel).where(RegisteredModel.workspace_id == workspace_id)
        if project_id is not None:
            statement = statement.where(RegisteredModel.project_id == project_id)
        statement = statement.order_by(RegisteredModel.updated_at.desc())
        return tuple(self._session.exec(statement).all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        name: str,
        description: str | None,
        base_model: str | None,
        tags: list[str],
        created_by: int | None,
    ) -> RegisteredModel:
        now = datetime.utcnow()
        model = RegisteredModel(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            description=description,
            base_model=base_model,
            tags=list(tags),
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return model

    def update(
        self,
        model: RegisteredModel,
        *,
        description: str | None = None,
        base_model: str | None = None,
        tags: list[str] | None = None,
        updated_by: int | None = None,
    ) -> RegisteredModel:
        if description is not None:
            model.description = description
        if base_model is not None:
            model.base_model = base_model
        if tags is not None:
            model.tags = list(tags)
        model.updated_at = datetime.utcnow()
        if updated_by is not None:
            model.updated_by = updated_by
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return model


class ModelVersionRepository:
    """Persist and query model versions."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_model(self, model_id: int) -> Sequence[ModelVersion]:
        statement = (
            select(ModelVersion)
            .where(ModelVersion.model_id == model_id)
            .order_by(ModelVersion.version.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get(self, version_id: int) -> ModelVersion | None:
        return self._session.get(ModelVersion, version_id)

    def get_by_number(self, *, model_id: int, version: int) -> ModelVersion | None:
        statement = (
            select(ModelVersion)
            .where(ModelVersion.model_id == model_id)
            .where(ModelVersion.version == version)
        )
        return self._session.exec(statement).first()

    def get_latest_version_number(self, model_id: int) -> int:
        statement = (
            select(ModelVersion.version)
            .where(ModelVersion.model_id == model_id)
            .order_by(ModelVersion.version.desc())
        )
        result = self._session.exec(statement).first()
        return int(result) if result is not None else 0

    def create(
        self,
        *,
        model_id: int,
        version: int,
        status: ModelVersionStatus,
        artifact_path: str | None,
        metadata_json: dict | None,
        training_run_id: int | None,
        evaluation_job_id: int | None,
        evaluation_metrics_json: dict | None,
        evaluation_report_path: str | None,
        deployment_target: str | None,
        notes: str | None,
        created_by: int | None,
    ) -> ModelVersion:
        now = datetime.utcnow()
        entry = ModelVersion(
            model_id=model_id,
            version=version,
            status=status,
            artifact_path=artifact_path,
            metadata_json=metadata_json,
            training_run_id=training_run_id,
            evaluation_job_id=evaluation_job_id,
            evaluation_metrics_json=evaluation_metrics_json,
            evaluation_report_path=evaluation_report_path,
            deployment_target=deployment_target,
            notes=notes,
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def update(
        self,
        version: ModelVersion,
        *,
        status: ModelVersionStatus | None = None,
        artifact_path: str | None = None,
        metadata_json: dict | None = None,
        evaluation_metrics_json: dict | None = None,
        evaluation_report_path: str | None = None,
        deployment_target: str | None = None,
        notes: str | None = None,
        updated_by: int | None = None,
        promoted_by: int | None = None,
        promoted_at: datetime | None = None,
    ) -> ModelVersion:
        if status is not None:
            version.status = status
        if artifact_path is not None:
            version.artifact_path = artifact_path
        if metadata_json is not None:
            version.metadata_json = metadata_json
        if evaluation_metrics_json is not None:
            version.evaluation_metrics_json = evaluation_metrics_json
        if evaluation_report_path is not None:
            version.evaluation_report_path = evaluation_report_path
        if deployment_target is not None:
            version.deployment_target = deployment_target
        if notes is not None:
            version.notes = notes
        if promoted_by is not None:
            version.promoted_by = promoted_by
        if promoted_at is not None:
            version.promoted_at = promoted_at
        if updated_by is not None:
            version.updated_by = updated_by
        version.updated_at = datetime.utcnow()
        self._session.add(version)
        self._session.flush()
        self._session.refresh(version)
        return version

"""Model registry domain service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    RegisteredModel,
    ModelVersion,
    ModelVersionStatus,
    TrainingRun,
    EvaluationJob,
    EvaluationJobStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.model_registry import RegisteredModelRepository, ModelVersionRepository
from app.repositories.training import TrainingRunRepository
from app.repositories.evaluation import EvaluationJobRepository
from app.repositories.workspace import WorkspaceRepository, ProjectRepository
from app.services.errors import (
    WorkspaceNotFoundError,
    ProjectNotFoundError,
    TrainingJobError,
    ModelRegistryError,
    ModelVersionPromotionError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


class ModelRegistryService:
    """Encapsulate registered model lifecycle operations."""

    def __init__(self, session: Session):
        self._session = session
        self._models = RegisteredModelRepository(session)
        self._versions = ModelVersionRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._projects = ProjectRepository(session)
        self._training_runs = TrainingRunRepository(session)
        self._evaluations = EvaluationJobRepository(session)
        self._audits = AuditLogRepository(session)
        self._permissions = PermissionService(session)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def list_models(
        self,
        *,
        workspace_id: int,
        current_user,
        project_id: int | None = None,
        status: ModelVersionStatus | None = None,
    ) -> list[dict[str, Any]]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_view(workspace.id, current_user)
        models = self._models.list_for_workspace(workspace_id=workspace.id, project_id=project_id)
        payload: list[dict[str, Any]] = []
        for model in models:
            model_dict = self._serialize_model(model)
            if status is not None:
                versions = [version for version in model_dict["versions"] if version["status"] == status.value]
                if not versions:
                    continue
                model_dict["versions"] = versions
            payload.append(model_dict)
        return payload

    def get_model(self, model_id: int, *, current_user) -> dict[str, Any]:
        model = self._load_model(model_id)
        self._require_view(model.workspace_id, current_user)
        return self._serialize_model(model)

    def create_model(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        name: str,
        description: str | None,
        base_model: str | None,
        tags: Iterable[str],
        current_user,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user, ip_address=ip_address, user_agent=user_agent)
        project = self._ensure_project(workspace.id, project_id) if project_id is not None else None

        if self._models.get_by_name(workspace_id=workspace.id, name=name):
            raise ModelRegistryError("同名模型已存在，请更换名称。")

        model = self._models.create(
            workspace_id=workspace.id,
            project_id=project.id if project else None,
            name=name,
            description=description,
            base_model=base_model,
            tags=list(tags),
            created_by=current_user.id,
        )
        self._session.commit()
        self._audits.record(
            event_type="model.registry.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace.id,
                "project_id": project.id if project else None,
                "model_id": model.id,
                "name": model.name,
            },
        )
        return self._serialize_model(model)

    def create_version(
        self,
        *,
        model_id: int,
        current_user,
        training_run_id: int | None,
        evaluation_job_id: int | None,
        metadata: dict | None,
        notes: str | None,
        deployment_target: str | None,
        artifact_path: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        model = self._load_model(model_id)
        self._require_manage(model.workspace_id, current_user, ip_address=ip_address, user_agent=user_agent)

        training_run: TrainingRun | None = None
        if training_run_id is not None:
            training_run = self._training_runs.get(training_run_id)
            if training_run is None or training_run.workspace_id != model.workspace_id:
                raise TrainingJobError("训练运行不存在或不属于该工作空间。")

        evaluation_job: EvaluationJob | None = None
        if evaluation_job_id is not None:
            evaluation_job = self._evaluations.get(evaluation_job_id)
            if evaluation_job is None or evaluation_job.workspace_id != model.workspace_id:
                raise ModelRegistryError("评估任务不存在或不属于该工作空间。")

        version_number = self._versions.get_latest_version_number(model.id) + 1
        relative_artifact_path = artifact_path or self._build_artifact_path(
            workspace_id=model.workspace_id,
            project_id=model.project_id,
            model_id=model.id,
            version=version_number,
        )

        evaluation_metrics = evaluation_job.metrics_json if evaluation_job else None
        evaluation_report_path = evaluation_job.report_path if evaluation_job else None
        metadata_payload = metadata or {}
        if training_run and training_run.metadata_json:
            metadata_payload = {
                **metadata_payload,
                "training": training_run.metadata_json,
            }
        if evaluation_job and evaluation_job.metrics_json:
            metadata_payload = {
                **metadata_payload,
                "evaluation": evaluation_job.metrics_json,
            }

        version = self._versions.create(
            model_id=model.id,
            version=version_number,
            status=ModelVersionStatus.CANDIDATE,
            artifact_path=relative_artifact_path,
            metadata_json=metadata_payload or None,
            training_run_id=training_run_id,
            evaluation_job_id=evaluation_job_id,
            evaluation_metrics_json=evaluation_metrics,
            evaluation_report_path=evaluation_report_path,
            deployment_target=deployment_target,
            notes=notes,
            created_by=current_user.id,
        )
        model.updated_at = datetime.utcnow()
        model.updated_by = current_user.id
        self._session.add(model)
        self._session.commit()

        self._audits.record(
            event_type="model.version.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": model.workspace_id,
                "project_id": model.project_id,
                "model_id": model.id,
                "model_version_id": version.id,
                "version": version.version,
                "status": version.status.value,
            },
        )
        return self._serialize_version(version)

    def update_version_status(
        self,
        *,
        model_id: int,
        version_id: int,
        target_status: ModelVersionStatus,
        current_user,
        notes: str | None,
        deployment_target: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        model = self._load_model(model_id)
        version = self._load_version(model, version_id)
        self._require_manage(model.workspace_id, current_user, ip_address=ip_address, user_agent=user_agent)

        if target_status == version.status and notes is None and deployment_target is None:
            return self._serialize_version(version)

        if target_status == ModelVersionStatus.PRODUCTION:
            self._ensure_evaluation_gate(version)
            version.promoted_by = current_user.id
            version.promoted_at = datetime.utcnow()
        elif target_status == ModelVersionStatus.CANDIDATE:
            version.promoted_by = None
            version.promoted_at = None

        updated_version = self._versions.update(
            version,
            status=target_status,
            deployment_target=deployment_target if deployment_target is not None else version.deployment_target,
            notes=notes if notes is not None else version.notes,
            updated_by=current_user.id,
        )

        self._session.commit()
        self._audits.record(
            event_type="model.version.status_changed",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": model.workspace_id,
                "project_id": model.project_id,
                "model_id": model.id,
                "model_version_id": version.id,
                "status": updated_version.status.value,
            },
        )
        return self._serialize_version(updated_version)

    def export_version_metadata(
        self,
        *,
        model_id: int,
        version_id: int,
        export_format: str,
        current_user,
    ) -> dict[str, Any]:
        model = self._load_model(model_id)
        version = self._load_version(model, version_id)
        self._require_view(model.workspace_id, current_user)

        export_format = export_format.lower()
        if export_format not in {"json", "markdown"}:
            raise ModelRegistryError("导出格式仅支持 json 或 markdown。")

        content = self._serialize_version(version)
        export_dir = self._build_export_directory(model.workspace_id, model.project_id, model.id)
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        extension = "md" if export_format == "markdown" else "json"
        filename = f"model-{model.id}-v{version.version}-{timestamp}.{extension}"
        export_path = export_dir / filename

        if export_format == "json":
            import json

            export_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            export_path.write_text(self._render_version_markdown(model, version, content), encoding="utf-8")

        relative_path = str(export_path.relative_to(Path(settings.workspace_storage_root).expanduser()))
        return {"path": relative_path, "format": export_format}

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
            raise ProjectNotFoundError("项目不存在或不属于指定的工作空间。")
        return project

    def _require_view(self, workspace_id: int, user, ip_address: str | None = None, user_agent: str | None = None):
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.EVALUATION_VIEW,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _require_manage(self, workspace_id: int, user, *, ip_address: str | None, user_agent: str | None):
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.DEPLOYMENT_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _load_model(self, model_id: int) -> RegisteredModel:
        model = self._models.get(model_id)
        if model is None:
            raise ModelRegistryError("模型不存在。")
        return model

    def _load_version(self, model: RegisteredModel, version_id: int) -> ModelVersion:
        version = self._versions.get(version_id)
        if version is None or version.model_id != model.id:
            raise ModelRegistryError("模型版本不存在。")
        return version

    def _build_artifact_path(self, *, workspace_id: int, project_id: int | None, model_id: int, version: int) -> str:
        root = Path(settings.workspace_storage_root).expanduser()
        workspace_segment = f"workspace-{workspace_id}"
        project_segment = f"project-{project_id}" if project_id is not None else "general"
        model_segment = f"model-{model_id}"
        version_segment = f"v{version}"
        target_dir = root / "models" / workspace_segment / project_segment / model_segment / version_segment
        target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir.relative_to(root))

    def _build_export_directory(self, workspace_id: int, project_id: int | None, model_id: int) -> Path:
        root = Path(settings.workspace_storage_root).expanduser()
        workspace_segment = f"workspace-{workspace_id}"
        project_segment = f"project-{project_id}" if project_id is not None else "general"
        model_segment = f"model-{model_id}"
        return root / "models" / workspace_segment / project_segment / model_segment / "exports"

    def _serialize_model(self, model: RegisteredModel) -> dict[str, Any]:
        versions = [self._serialize_version(version) for version in self._versions.list_for_model(model.id)]
        return {
            "id": model.id,
            "workspace_id": model.workspace_id,
            "project_id": model.project_id,
            "name": model.name,
            "description": model.description,
            "base_model": model.base_model,
            "tags": model.tags or [],
            "created_by": model.created_by,
            "updated_by": model.updated_by,
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
            "versions": versions,
        }

    def _serialize_version(self, version: ModelVersion) -> dict[str, Any]:
        return {
            "id": version.id,
            "model_id": version.model_id,
            "version": version.version,
            "status": version.status.value,
            "artifact_path": version.artifact_path,
            "metadata": version.metadata_json or {},
            "training_run_id": version.training_run_id,
            "evaluation_job_id": version.evaluation_job_id,
            "evaluation_metrics": version.evaluation_metrics_json or {},
            "evaluation_report_path": version.evaluation_report_path,
            "deployment_target": version.deployment_target,
            "notes": version.notes,
            "created_by": version.created_by,
            "updated_by": version.updated_by,
            "promoted_by": version.promoted_by,
            "promoted_at": version.promoted_at.isoformat() if version.promoted_at else None,
            "created_at": version.created_at.isoformat(),
            "updated_at": version.updated_at.isoformat(),
        }

    def _ensure_evaluation_gate(self, version: ModelVersion) -> None:
        if version.evaluation_job_id is None:
            raise ModelVersionPromotionError("需要提供通过评估的结果才能发布为生产版本。")
        evaluation = self._evaluations.get(version.evaluation_job_id)
        if evaluation is None or evaluation.status != EvaluationJobStatus.COMPLETED:
            raise ModelVersionPromotionError("评估尚未完成，无法发布为生产版本。")
        metrics = evaluation.metrics_json or {}
        thresholds = metrics.get("thresholds") if isinstance(metrics, dict) else None
        if thresholds and any(info.get("triggered") for info in thresholds.values() if isinstance(info, dict)):
            raise ModelVersionPromotionError("评估指标未全部达标，无法发布为生产版本。")

    def _render_version_markdown(
        self,
        model: RegisteredModel,
        version: ModelVersion,
        payload: dict[str, Any],
    ) -> str:
        lines = [
            f"# 模型版本导出 - {model.name} v{version.version}",
            "",
            f"- 模型 ID：{model.id}",
            f"- 版本状态：{version.status.value}",
            f"- 训练运行：{version.training_run_id or '无'}",
            f"- 评估任务：{version.evaluation_job_id or '无'}",
            f"- Artefact：`{version.artifact_path or '未提交'}`",
            "",
            "## 备注",
            version.notes or "（无）",
            "",
            "## 元数据",
        ]
        metadata = payload.get("metadata") or {}
        if metadata:
            import json

            lines.append("```json")
            lines.append(json.dumps(metadata, ensure_ascii=False, indent=2))
            lines.append("```")
        else:
            lines.append("（无）")
        return "\n".join(lines)

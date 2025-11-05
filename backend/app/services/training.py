"""Training templates and job orchestration service."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    DatasetFormatStatus,
    DatasetFormatVersion,
    DatasetVersion,
    Project,
    TrainingAdapterType,
    TrainingEvent,
    TrainingJob,
    TrainingJobStatus,
    TrainingRun,
    TrainingTemplate,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.dataset import DatasetRepository, DatasetVersionRepository
from app.repositories.format import DatasetFormatVersionRepository
from app.repositories.training import (
    TrainingEventRepository,
    TrainingJobRepository,
    TrainingRunRepository,
    TrainingTemplateRepository,
    TrainingWizardDraftRepository,
)
from app.repositories.workspace import ProjectRepository, WorkspaceRepository
from app.services.errors import (
    DatasetNotFoundError,
    DatasetVersionError,
    TrainingJobError,
    TrainingTemplateError,
    TrainingValidationError,
    WorkspaceNotFoundError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation
from app.tasks.training import run_training_job
from app.services.evaluation import EvaluationService


BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "LoRA 默认模板",
        "base_model": "meta-llama/Llama-3-8b-instruct",
        "adapter_type": TrainingAdapterType.LORA,
        "description": "适用于通用中文指令微调的 LoRA 模板，提供稳定的学习率与 rank 参数。",
        "params": {
            "learning_rate": 5e-4,
            "lora_rank": 16,
            "lora_alpha": 32,
            "num_epochs": 3,
            "per_device_train_batch_size": 4,
            "gradient_accumulation_steps": 4,
        },
    },
    {
        "name": "QLoRA 低显存模板",
        "base_model": "meta-llama/Llama-3-8b-instruct",
        "adapter_type": TrainingAdapterType.QLORA,
        "description": "针对 24GB 显存环境优化的 QLoRA 配置，使用双量化与更小的 rank。",
        "params": {
            "learning_rate": 2e-4,
            "lora_rank": 8,
            "quantization": "nf4-int4",
            "num_epochs": 2,
            "per_device_train_batch_size": 2,
            "gradient_accumulation_steps": 8,
        },
    },
    {
        "name": "DoRA 高保真模板",
        "base_model": "meta-llama/Llama-3-70b-instruct",
        "adapter_type": TrainingAdapterType.DORA,
        "description": "面向大模型高精度微调的 DoRA 模板，适用于对齐与专业领域训练。",
        "params": {
            "learning_rate": 1e-4,
            "lora_rank": 32,
            "num_epochs": 1,
            "per_device_train_batch_size": 1,
            "gradient_checkpointing": True,
        },
    },
]

PARAMETER_RULES: dict[str, dict[str, Any]] = {
    "learning_rate": {"min": 1e-7, "max": 1e-2, "type": float, "hint": "建议范围 1e-5 ~ 5e-4"},
    "lora_rank": {"min": 1, "max": 256, "type": int, "hint": "常用 8/16/32"},
    "lora_alpha": {"min": 1, "max": 4096, "type": int, "hint": "默认 16~64 足够"},
    "num_epochs": {"min": 1, "max": 50, "type": int, "hint": "建议 1~5 个 epoch"},
    "per_device_train_batch_size": {"min": 1, "max": 128, "type": int, "hint": "建议根据显存设置 1~8"},
    "gradient_accumulation_steps": {"min": 1, "max": 256, "type": int, "hint": "过大将影响收敛"},
    "warmup_steps": {"min": 0, "max": 5000, "type": int, "hint": "常用 0 或 100~500"},
}


class TrainingService:
    """High-level orchestration for training templates and jobs."""

    def __init__(self, session: Session):
        self._session = session
        self._templates = TrainingTemplateRepository(session)
        self._jobs = TrainingJobRepository(session)
        self._runs = TrainingRunRepository(session)
        self._events = TrainingEventRepository(session)
        self._datasets = DatasetRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._formats = DatasetFormatVersionRepository(session)
        self._drafts = TrainingWizardDraftRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._projects = ProjectRepository(session)
        self._audits = AuditLogRepository(session)
        self._permissions = PermissionService(session)

    @contextmanager
    def _transaction(self):
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield

    # ------------------------------------------------------------------ #
    # Template management
    # ------------------------------------------------------------------ #

    def list_templates(
        self,
        *,
        workspace_id: int,
        current_user: User,
    ) -> list[TrainingTemplate]:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        self._ensure_builtin_templates(workspace_id)
        return list(self._templates.list_for_workspace(workspace_id))

    def create_template(
        self,
        *,
        workspace_id: int,
        name: str,
        base_model: str,
        adapter_type: TrainingAdapterType,
        params: Mapping[str, Any] | None,
        description: str | None,
        current_user: User,
    ) -> TrainingTemplate:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

        validated_params = self._validate_parameters(params or {})
        with self._transaction():
            template = self._templates.create(
                workspace_id=workspace_id,
                name=name.strip(),
                base_model=base_model.strip(),
                adapter_type=adapter_type,
                params=validated_params,
                description=description.strip() if description else None,
                created_by=current_user.id,
                is_builtin=False,
            )
        return template

    def update_template(
        self,
        *,
        template_id: int,
        name: str | None,
        description: str | None,
        base_model: str | None,
        adapter_type: TrainingAdapterType | None,
        params: Mapping[str, Any] | None,
        current_user: User,
    ) -> TrainingTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise TrainingTemplateError("训练模板不存在")

        self._permissions.require_operation(
            workspace_id=template.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        if template.is_builtin:
            raise TrainingTemplateError("系统模板不可直接修改，请先克隆后编辑")

        validated_params = self._validate_parameters(params or template.params_json)
        with self._transaction():
            updated = self._templates.update(
                template,
                name=name.strip() if name else None,
                description=description.strip() if description is not None else None,
                base_model=base_model.strip() if base_model else None,
                adapter_type=adapter_type,
                params=validated_params,
            )
        return updated

    def clone_template(
        self,
        *,
        template_id: int,
        name: str | None,
        current_user: User,
    ) -> TrainingTemplate:
        source = self._templates.get(template_id)
        if source is None:
            raise TrainingTemplateError("训练模板不存在")

        self._permissions.require_operation(
            workspace_id=source.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

        clone_name = name.strip() if name else f"{source.name} 副本"
        with self._transaction():
            template = self._templates.create(
                workspace_id=source.workspace_id,
                name=clone_name,
                base_model=source.base_model,
                adapter_type=source.adapter_type,
                params=deepcopy(source.params_json),
                description=source.description,
                created_by=current_user.id,
                is_builtin=False,
            )
        return template

    def delete_template(
        self,
        *,
        template_id: int,
        current_user: User,
    ) -> None:
        template = self._templates.get(template_id)
        if template is None:
            raise TrainingTemplateError("训练模板不存在")

        self._permissions.require_operation(
            workspace_id=template.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        if template.is_builtin:
            raise TrainingTemplateError("系统模板不可删除")
        if self._jobs.exists_for_template(template_id):
            raise TrainingTemplateError("模板已被训练任务引用，无法删除，请先清理相关任务。")

        with self._transaction():
            self._templates.delete(template)

    # ------------------------------------------------------------------ #
    # Job management
    # ------------------------------------------------------------------ #

    def create_job(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        dataset_version_id: int,
        dataset_format_version_id: int | None,
        template_id: int | None,
        base_model: str | None,
        adapter_type: TrainingAdapterType | None,
        params: Mapping[str, Any] | None,
        requested_gpus: int | None,
        queue_name: str | None,
        notes: str | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TrainingJob:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        config = self._build_training_configuration(
            workspace_id=workspace_id,
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            dataset_format_version_id=dataset_format_version_id,
            template_id=template_id,
            base_model=base_model,
            adapter_type=adapter_type,
            params=params,
            requested_gpus=requested_gpus,
            queue_name=queue_name,
        )

        dataset_version = config["dataset_version"]
        dataset_format = config["dataset_format"]
        template = config["template"]
        resource_plan = config["resource_plan"]

        job = TrainingJob(
            workspace_id=workspace_id,
            project_id=project_id,
            dataset_version_id=dataset_version.id,
            dataset_format_version_id=dataset_format.id if dataset_format else None,
            training_template_id=template.id if template else None,
            base_model=config["base_model"],
            adapter_type=config["adapter_type"],
            status=TrainingJobStatus.PENDING,
            params_json=config["params"],
            notes=notes.strip() if notes else None,
            scheduled_by=current_user.id,
            requested_gpus=resource_plan["requested_gpus"],
            queue_name=resource_plan["queue_name"],
        )

        with self._transaction():
            job = self._jobs.create(job)

        self._audits.record(
            event_type="training.job.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "job_id": job.id,
                "dataset_version_id": dataset_version.id,
                "template_id": template.id if template else None,
                "requested_gpus": resource_plan["requested_gpus"],
                "queue_name": resource_plan["queue_name"],
            },
        )

        run_training_job.delay(job.id)
        return job

    def get_job(self, job_id: int, current_user: User) -> TrainingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingJobError("训练任务不存在")

        self._permissions.require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        return job

    def get_job_with_latest_run(
        self,
        job_id: int,
        current_user: User,
    ) -> tuple[TrainingJob, TrainingRun | None]:
        self._session.expire_all()
        job = self.get_job(job_id, current_user)
        run = self._runs.get_latest_for_job(job.id)
        return job, run

    def list_feedback_summaries(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        limit: int,
        current_user: User,
    ) -> dict[str, Any]:
        evaluation_service = EvaluationService(self._session)
        return evaluation_service.list_feedback_summaries(
            workspace_id=workspace_id,
            project_id=project_id,
            current_user=current_user,
            limit=limit,
        )

    # ------------------------------------------------------------------ #
    # Wizard draft & validation
    # ------------------------------------------------------------------ #

    def get_wizard_draft(
        self,
        *,
        workspace_id: int,
        current_user: User,
    ) -> dict[str, Any] | None:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )
        draft = self._drafts.get(workspace_id=workspace_id, user_id=current_user.id)
        if draft is None:
            return None
        return {
            "workspace_id": workspace_id,
            "payload": draft.payload_json,
            "updated_at": draft.updated_at,
        }

    def save_wizard_draft(
        self,
        *,
        workspace_id: int,
        payload: Mapping[str, Any] | None,
        current_user: User,
    ) -> dict[str, Any]:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

        payload_dict = dict(payload or {})
        with self._transaction():
            if not payload_dict:
                self._drafts.delete(workspace_id=workspace_id, user_id=current_user.id)
                draft = None
            else:
                draft = self._drafts.upsert(
                    workspace_id=workspace_id,
                    user_id=current_user.id,
                    payload=payload_dict,
                )
        event_type = "training.wizard.draft.cleared" if not payload_dict else "training.wizard.draft.saved"
        self._audits.record(
            event_type=event_type,
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={"workspace_id": workspace_id},
        )
        if draft is None:
            return {"workspace_id": workspace_id, "payload": None, "updated_at": None}
        return {
            "workspace_id": workspace_id,
            "payload": draft.payload_json,
            "updated_at": draft.updated_at,
        }

    def validate_wizard_configuration(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        dataset_version_id: int,
        dataset_format_version_id: int | None,
        template_id: int | None,
        base_model: str | None,
        adapter_type: TrainingAdapterType | None,
        params: Mapping[str, Any] | None,
        requested_gpus: int | None,
        queue_name: str | None,
        current_user: User,
    ) -> dict[str, Any]:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
            ip_address=None,
            user_agent=None,
        )

        config = self._build_training_configuration(
            workspace_id=workspace_id,
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            dataset_format_version_id=dataset_format_version_id,
            template_id=template_id,
            base_model=base_model,
            adapter_type=adapter_type,
            params=params,
            requested_gpus=requested_gpus,
            queue_name=queue_name,
        )

        dataset_version = config["dataset_version"]
        dataset_format = config["dataset_format"]
        template = config["template"]
        resource_plan = config["resource_plan"]

        return {
            "workspace_id": workspace_id,
            "project_id": project_id,
            "dataset_version_id": dataset_version.id,
            "dataset_format_version_id": dataset_format.id if dataset_format else None,
            "training_template_id": template.id if template else None,
            "base_model": config["base_model"],
            "adapter_type": config["adapter_type"],
            "params": config["params"],
            "requested_gpus": resource_plan["requested_gpus"],
            "queue_name": resource_plan["queue_name"],
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _ensure_builtin_templates(self, workspace_id: int) -> None:
        existing = self._templates.list_for_workspace(workspace_id)
        existing_names = {template.name for template in existing if template.is_builtin}
        to_create = [
            template_def
            for template_def in BUILTIN_TEMPLATES
            if template_def["name"] not in existing_names
        ]
        if not to_create:
            return
        with self._transaction():
            for template_def in to_create:
                self._templates.create(
                    workspace_id=workspace_id,
                    name=template_def["name"],
                    base_model=template_def["base_model"],
                    adapter_type=template_def["adapter_type"],
                    params=template_def["params"],
                    description=template_def.get("description"),
                    created_by=None,
                    is_builtin=True,
                )

    def _validate_parameters(self, params: Mapping[str, Any]) -> dict:
        validated: dict[str, Any] = {}
        for key, value in params.items():
            if key not in PARAMETER_RULES:
                validated[key] = value
                continue
            rule = PARAMETER_RULES[key]
            expected_type = rule["type"]
            try:
                cast_value = expected_type(value)
            except (TypeError, ValueError) as exc:
                raise TrainingValidationError(f"{key} 类型无效，应为 {expected_type.__name__}") from exc
            min_value = rule["min"]
            max_value = rule["max"]
            if cast_value < min_value or cast_value > max_value:
                hint = rule.get("hint", "")
                message = f"{key} 超出允许范围 [{min_value}, {max_value}]"
                if hint:
                    message = f"{message}。建议：{hint}"
                raise TrainingValidationError(message)
            validated[key] = cast_value
        return validated

    def _load_dataset_version(self, dataset_version_id: int, workspace_id: int) -> DatasetVersion:
        version = self._versions.get(dataset_version_id)
        if version is None:
            raise DatasetNotFoundError("数据集版本不存在")
        dataset = self._datasets.get(version.dataset_id)
        if dataset is None or dataset.workspace_id != workspace_id:
            raise DatasetVersionError("数据集版本不属于当前工作空间")
        if version.quality_summary_path is None:
            raise DatasetVersionError("请先完成质量评估后再发起训练")
        return version

    def _resolve_dataset_format(
        self,
        version: DatasetVersion,
        dataset_format_version_id: int | None,
    ) -> DatasetFormatVersion | None:
        if dataset_format_version_id is not None:
            record = self._formats.get(dataset_format_version_id)
            if (
                record is None
                or record.dataset_version_id != version.id
                or record.status != DatasetFormatStatus.COMPLETED
            ):
                raise TrainingJobError("指定的标准化格式不存在或尚未完成")
            return record

        records = self._formats.list_for_version(version.id)
        for record in records:
            if record.is_active and record.status == DatasetFormatStatus.COMPLETED:
                return record
        for record in records:
            if record.status == DatasetFormatStatus.COMPLETED:
                return record
        raise TrainingJobError("请先生成可用的标准化数据格式后再启动训练")

    def _normalize_resource_plan(
        self,
        *,
        requested_gpus: int | None,
        queue_name: str | None,
    ) -> dict[str, Any]:
        gpus = requested_gpus if requested_gpus is not None else 1
        try:
            gpus = int(gpus)
        except (TypeError, ValueError) as exc:
            raise TrainingValidationError("GPU 数量必须为整数。") from exc
        if gpus < 1:
            raise TrainingValidationError("GPU 数量至少为 1。")
        if gpus > settings.max_training_gpus:
            raise TrainingValidationError(
                f"当前环境最多支持 {settings.max_training_gpus} 张 GPU。"
            )
        if gpus > 1 and not settings.allow_parallel_gpu:
            raise TrainingValidationError("当前配置不支持多卡并行，请将 GPU 数量设置为 1。")

        available_queues = tuple(settings.training_gpu_queues)
        queue_value = (queue_name or (available_queues[0] if available_queues else "default")).strip()
        if not queue_value:
            raise TrainingValidationError("必须指定训练队列。")
        normalized_queue = None
        for defined in available_queues:
            if queue_value.lower() == defined.lower():
                normalized_queue = defined
                break
        if normalized_queue is None:
            choices = "、".join(available_queues) if available_queues else "default"
            raise TrainingValidationError(f"训练队列无效，请从 {choices} 中选择。")

        return {
            "requested_gpus": gpus,
            "queue_name": normalized_queue,
        }

    def _build_training_configuration(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        dataset_version_id: int,
        dataset_format_version_id: int | None,
        template_id: int | None,
        base_model: str | None,
        adapter_type: TrainingAdapterType | None,
        params: Mapping[str, Any] | None,
        requested_gpus: int | None,
        queue_name: str | None,
    ) -> dict[str, Any]:
        dataset_version = self._load_dataset_version(dataset_version_id, workspace_id)
        dataset_format = self._resolve_dataset_format(dataset_version, dataset_format_version_id)

        template = self._templates.get(template_id) if template_id else None
        if template and template.workspace_id != workspace_id:
            raise TrainingJobError("模板不属于当前工作空间")

        base_model_value = (base_model or template.base_model if template else base_model or "").strip()
        if not base_model_value:
            raise TrainingJobError("必须指定基座模型")

        adapter_value = adapter_type or (template.adapter_type if template else TrainingAdapterType.LORA)

        template_params: dict[str, Any] = template.params_json if template else {}
        merged_params = dict(template_params)
        if params:
            merged_params.update(params)
        validated_params = self._validate_parameters(merged_params)

        project = None
        if project_id is not None:
            project = self._session.get(Project, project_id)
            if project is None or project.workspace_id != workspace_id:
                raise TrainingJobError("项目不存在或不属于当前工作空间")

        resource_plan = self._normalize_resource_plan(
            requested_gpus=requested_gpus,
            queue_name=queue_name,
        )

        return {
            "dataset_version": dataset_version,
            "dataset_format": dataset_format,
            "template": template,
            "base_model": base_model_value,
            "adapter_type": adapter_value,
            "params": validated_params,
            "project": project,
            "resource_plan": resource_plan,
        }


def build_training_event(session: Session, run: TrainingRun, level: str, message: str) -> TrainingEvent:
    """Create and persist a training event helper (used by Celery task)."""
    repo = TrainingEventRepository(session)
    return repo.create(run_id=run.id, level=level, message=message)

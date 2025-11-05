"""Evaluation template and job orchestration service."""

from __future__ import annotations

import html
import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

from jose import ExpiredSignatureError, JWTError, jwt

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    EvaluationTemplate,
    EvaluationTaskType,
    EvaluationJob,
    EvaluationJobStatus,
    EvaluationTriggerMode,
    TrainingRun,
    TrainingJob,
    DatasetVersion,
    Workspace,
    Project,
    User,
    EvaluationFeedback,
    EvaluationFeedbackKind,
    EvaluationFeedbackStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.dataset import DatasetVersionRepository
from app.repositories.evaluation import (
    EvaluationTemplateRepository,
    EvaluationJobRepository,
    EvaluationFeedbackRepository,
)
from app.repositories.training import TrainingRunRepository, TrainingJobRepository
from app.repositories.workspace import WorkspaceRepository, ProjectRepository
from app.services.errors import (
    WorkspaceNotFoundError,
    TrainingJobError,
    DatasetNotFoundError,
    TrainingValidationError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation
from app.tasks.evaluation import run_evaluation_job


@dataclass(slots=True)
class UploadedEvaluationDataset:
    """In-memory representation of an uploaded evaluation dataset."""

    filename: str
    content: bytes
    content_type: str | None


BUILTIN_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "key": "qa-default",
        "name": "问答模板",
        "description": "针对知识库问答场景，计算准确率、召回率与平均响应长度。",
        "task_type": EvaluationTaskType.QA,
        "metrics": ["accuracy", "recall", "avg_response_tokens"],
        "config": {"expected_format": "jsonl", "schema": {"prompt": "str", "answer": "str"}},
    },
    {
        "key": "conversation-default",
        "name": "多轮对话模板",
        "description": "模拟客服对话，关注 turn 完成率与情绪评分。",
        "task_type": EvaluationTaskType.CONVERSATION,
        "metrics": ["completion_rate", "sentiment_score", "avg_latency_ms"],
        "config": {"expected_format": "jsonl", "schema": {"dialog": "list[str]"}},
    },
    {
        "key": "classification-default",
        "name": "分类模板",
        "description": "适用于文本分类与标签推荐，输出 F1 与混淆矩阵摘要。",
        "task_type": EvaluationTaskType.CLASSIFICATION,
        "metrics": ["precision", "recall", "f1_score"],
        "config": {"expected_format": "jsonl", "schema": {"text": "str", "label": "str"}},
    },
)


class EvaluationService:
    """High-level coordination for evaluation templates and jobs."""

    DEFAULT_AUTOMATION_TEMPLATE_KEY = "qa-default"
    AUTOMATION_TEMPLATE_PARAM_KEY = "evaluation_template_id"
    AUTOMATION_DATASET_PARAM_KEY = "evaluation_dataset_version_id"
    SHARE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
    SHARE_TOKEN_AUDIENCE = "evaluation-report-share"
    PDF_TITLE = "LLM Fine-tune Evaluation Report"

    def __init__(self, session: Session):
        self._session = session
        self._templates = EvaluationTemplateRepository(session)
        self._jobs = EvaluationJobRepository(session)
        self._feedback = EvaluationFeedbackRepository(session)
        self._runs = TrainingRunRepository(session)
        self._training_jobs = TrainingJobRepository(session)
        self._versions = DatasetVersionRepository(session)
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
    ) -> list[EvaluationTemplate]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_operation(
            workspace_id=workspace.id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )
        self._ensure_builtin_templates()
        return list(self._templates.list_for_workspace(workspace.id))

    def get_template(self, template_id: int, *, current_user: User) -> EvaluationTemplate:
        template = self._templates.get(template_id)
        if template is None:
            raise TrainingValidationError("评估模板不存在")
        workspace_id = template.workspace_id or self._infer_workspace_from_user(current_user)
        if workspace_id is not None:
            self._require_operation(
                workspace_id=workspace_id,
                user=current_user,
                operation=RoleOperation.EVALUATION_VIEW,
            )
        return template

    def _ensure_builtin_templates(self) -> None:
        existing = {template.key for template in self._templates.list_all()}
        created = False
        for payload in BUILTIN_TEMPLATES:
            if payload["key"] in existing:
                continue
            self._templates.create(
                key=payload["key"],
                name=payload["name"],
                description=payload["description"],
                task_type=payload["task_type"],
                metrics=payload["metrics"],
                config=payload["config"],
                is_builtin=True,
                workspace_id=None,
            )
            existing.add(payload["key"])
            created = True
        if created:
            self._session.commit()

    def _infer_workspace_from_user(self, user: User) -> int | None:
        memberships = getattr(user, "memberships", None)
        if memberships:
            return memberships[0].workspace_id
        return None

    # ------------------------------------------------------------------ #
    # Job management
    # ------------------------------------------------------------------ #

    def create_job(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        training_run_id: int | None,
        evaluation_template_id: int,
        dataset_version_id: int | None,
        dataset_file: UploadedEvaluationDataset | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EvaluationJob:
        workspace = self._ensure_workspace(workspace_id)
        self._require_operation(
            workspace_id=workspace.id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )

        template = self._templates.get(evaluation_template_id)
        if template is None:
            raise TrainingValidationError("评估模板不存在")

        project: Project | None = None
        if project_id is not None:
            project = self._projects.get(project_id)
            if project is None or project.workspace_id != workspace.id:
                raise TrainingValidationError("项目不存在或不属于当前工作空间")

        training_run: TrainingRun | None = None
        if training_run_id is not None:
            training_run = self._runs.get(training_run_id)
            if training_run is None or training_run.job.workspace_id != workspace.id:
                raise TrainingJobError("训练运行不存在或不属于当前工作空间")

        dataset_version: DatasetVersion | None = None
        if dataset_version_id is not None:
            dataset_version = self._versions.get(dataset_version_id)
            if (
                dataset_version is None
                or dataset_version.dataset.workspace_id != workspace.id
            ):
                raise DatasetNotFoundError("数据版本不存在或不属于当前工作空间")

        if dataset_version is None and dataset_file is None:
            raise TrainingValidationError("请上传测试集或指定数据版本。")

        job = EvaluationJob(
            workspace_id=workspace.id,
            project_id=project.id if project else None,
            training_run_id=training_run.id if training_run else None,
            evaluation_template_id=template.id,
            dataset_version_id=dataset_version.id if dataset_version else None,
            created_by=current_user.id,
            status=EvaluationJobStatus.PENDING,
            trigger_mode=EvaluationTriggerMode.MANUAL,
        )

        with self._transaction():
            job = self._jobs.create(job)
            self._prepare_artifacts(
                job=job,
                dataset_version=dataset_version,
                dataset_file=dataset_file,
            )
            self._jobs.update(job, status=EvaluationJobStatus.PENDING)

        self._audits.record(
            event_type="evaluation.job.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace.id,
                "evaluation_job_id": job.id,
                "template_id": template.id,
                "training_run_id": training_run.id if training_run else None,
                "dataset_version_id": dataset_version.id if dataset_version else None,
            },
        )

        run_evaluation_job.delay(job.id)
        return job

    def schedule_automatic_evaluation(
        self,
        *,
        training_run: TrainingRun,
        job: TrainingJob | None = None,
    ) -> EvaluationJob | None:
        """Create an evaluation job for a completed training run if needed."""
        job = job or training_run.job or self._training_jobs.get(training_run.job_id)
        if job is None:
            return None

        workspace = self._ensure_workspace(job.workspace_id)
        self._ensure_builtin_templates()
        template = self._resolve_automation_template(job=job, workspace_id=workspace.id)
        if template is None:
            return None

        existing = self._jobs.find_by_run_and_template(
            training_run_id=training_run.id,
            evaluation_template_id=template.id,
        )
        if existing:
            return existing

        dataset_version = self._resolve_automation_dataset(job=job, training_run=training_run)
        if dataset_version is None:
            return None

        evaluation_job = EvaluationJob(
            workspace_id=workspace.id,
            project_id=job.project_id,
            training_run_id=training_run.id,
            evaluation_template_id=template.id,
            dataset_version_id=dataset_version.id,
            created_by=job.scheduled_by,
            status=EvaluationJobStatus.PENDING,
            trigger_mode=EvaluationTriggerMode.AUTOMATIC,
        )

        with self._transaction():
            evaluation_job = self._jobs.create(evaluation_job)
            self._prepare_artifacts(
                job=evaluation_job,
                dataset_version=dataset_version,
                dataset_file=None,
            )
            self._jobs.update(evaluation_job, status=EvaluationJobStatus.PENDING)

        self._audits.record(
            event_type="evaluation.job.auto_created",
            user_id=job.scheduled_by,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace.id,
                "evaluation_job_id": evaluation_job.id,
                "training_run_id": training_run.id,
                "template_id": template.id,
                "dataset_version_id": dataset_version.id,
            },
        )

        run_evaluation_job.delay(evaluation_job.id)
        return evaluation_job

    def _resolve_automation_template(
        self,
        *,
        job: TrainingJob,
        workspace_id: int,
    ) -> EvaluationTemplate | None:
        template_id: int | None = None
        evaluation_config = {}
        params = job.params_json or {}
        if isinstance(params, dict):
            evaluation_config = params.get("evaluation") or {}
            template_id = evaluation_config.get("template_id") or evaluation_config.get(
                self.AUTOMATION_TEMPLATE_PARAM_KEY
            )
            if template_id is None:
                template_id = params.get(self.AUTOMATION_TEMPLATE_PARAM_KEY)

        template: EvaluationTemplate | None = None
        if template_id is not None:
            template = self._templates.get(template_id)

        if template is None:
            # Prefer workspace-specific templates, fallback to builtins (qa-default)
            candidates: Sequence[EvaluationTemplate] = self._templates.list_for_workspace(workspace_id)
            for candidate in candidates:
                if candidate.key == self.DEFAULT_AUTOMATION_TEMPLATE_KEY:
                    template = candidate
                    break
            if template is None and candidates:
                template = candidates[0]
            if template is None:
                template = self._templates.get_by_key(self.DEFAULT_AUTOMATION_TEMPLATE_KEY)
        return template

    def _resolve_automation_dataset(
        self,
        *,
        job: TrainingJob,
        training_run: TrainingRun,
    ) -> DatasetVersion | None:
        dataset_version_id: int | None = None
        params = job.params_json or {}
        evaluation_config = {}
        if isinstance(params, dict):
            evaluation_config = params.get("evaluation") or {}
            dataset_version_id = evaluation_config.get("dataset_version_id") or evaluation_config.get(
                self.AUTOMATION_DATASET_PARAM_KEY
            )
            if dataset_version_id is None:
                dataset_version_id = params.get(self.AUTOMATION_DATASET_PARAM_KEY)

        if dataset_version_id is None:
            dataset_version_id = job.dataset_version_id

        dataset_version: DatasetVersion | None = None
        if dataset_version_id is not None:
            dataset_version = self._versions.get(dataset_version_id)

        if dataset_version is None and training_run.metadata_json:
            metadata = training_run.metadata_json or {}
            dataset_info = metadata.get("dataset") or {}
            dataset_version_id = dataset_info.get("version_id")
            if dataset_version_id:
                dataset_version = self._versions.get(dataset_version_id)

        return dataset_version

    def list_jobs(
        self,
        *,
        workspace_id: int,
        current_user: User,
        training_run_id: int | None = None,
    ) -> list[EvaluationJob]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_operation(
            workspace_id=workspace.id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )
        return list(
            self._jobs.list_for_workspace(
                workspace.id,
                training_run_id=training_run_id,
            )
        )

    def get_job(
        self,
        job_id: int,
        *,
        current_user: User,
    ) -> EvaluationJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")
        self._require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )
        return job

    # ------------------------------------------------------------------ #
    # Feedback management
    # ------------------------------------------------------------------ #

    def list_feedback(
        self,
        job_id: int,
        *,
        current_user: User,
        status: EvaluationFeedbackStatus | None = None,
        kind: EvaluationFeedbackKind | None = None,
        tag: str | None = None,
    ) -> list[EvaluationFeedback]:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")
        self._require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )
        entries = self._feedback.list_for_job(job_id)
        filtered: list[EvaluationFeedback] = []
        tag_value = tag.strip() if tag else None
        for entry in entries:
            if status is not None and entry.status != status:
                continue
            if kind is not None and entry.kind != kind:
                continue
            if tag_value and tag_value not in entry.tags:
                continue
            filtered.append(entry)
        return filtered

    def create_feedback(
        self,
        job_id: int,
        *,
        workspace_id: int,
        current_user: User,
        kind: EvaluationFeedbackKind,
        body: str,
        tags: list[str],
        status: EvaluationFeedbackStatus | None = None,
        training_run_id: int | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EvaluationFeedback:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")
        if job.workspace_id != workspace_id:
            raise TrainingValidationError("工作空间与评估任务不匹配")

        self._permissions.require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        trimmed_body = body.strip()
        if not trimmed_body:
            raise TrainingValidationError("反馈内容不能为空")

        normalized_tags = [item.strip() for item in tags if item and item.strip()]
        entry_status = status or EvaluationFeedbackStatus.OPEN
        if kind == EvaluationFeedbackKind.BUSINESS_METRIC and not metric_name:
            raise TrainingValidationError("业务指标需要填写名称")

        entry = self._feedback.create(
            workspace_id=job.workspace_id,
            project_id=job.project_id,
            evaluation_job_id=job.id,
            training_run_id=training_run_id,
            kind=kind,
            status=entry_status,
            body=trimmed_body,
            tags=normalized_tags,
            metric_name=metric_name.strip() if metric_name else None,
            metric_value=metric_value,
            created_by=current_user.id,
        )

        self._audits.record(
            event_type="evaluation.feedback.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "feedback_id": entry.id,
                "kind": entry.kind.value,
            },
        )
        return entry

    def update_feedback(
        self,
        *,
        job_id: int,
        feedback_id: int,
        current_user: User,
        body: str | None = None,
        status: EvaluationFeedbackStatus | None = None,
        tags: list[str] | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EvaluationFeedback:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")

        entry = self._feedback.get(feedback_id)
        if entry is None or entry.evaluation_job_id != job.id:
            raise TrainingValidationError("反馈记录不存在")

        self._permissions.require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        trimmed_body = body.strip() if body is not None else None
        normalized_tags = [item.strip() for item in tags] if tags is not None else None
        resolved_at = entry.resolved_at
        resolved_by = entry.resolved_by
        new_status = status or entry.status
        if new_status == EvaluationFeedbackStatus.RESOLVED and entry.status != EvaluationFeedbackStatus.RESOLVED:
            resolved_at = datetime.utcnow()
            resolved_by = current_user.id
        elif new_status == EvaluationFeedbackStatus.OPEN and entry.status == EvaluationFeedbackStatus.RESOLVED:
            resolved_at = None
            resolved_by = None

        updated_entry = self._feedback.update(
            entry,
            body=trimmed_body,
            status=new_status,
            tags=normalized_tags,
            metric_name=metric_name.strip() if metric_name is not None and metric_name else metric_name,
            metric_value=metric_value,
            updated_by=current_user.id,
            resolved_by=resolved_by,
            resolved_at=resolved_at,
        )

        self._audits.record(
            event_type="evaluation.feedback.updated",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "feedback_id": updated_entry.id,
                "status": updated_entry.status.value,
            },
        )
        return updated_entry

    def delete_feedback(
        self,
        *,
        job_id: int,
        feedback_id: int,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")

        entry = self._feedback.get(feedback_id)
        if entry is None or entry.evaluation_job_id != job.id:
            raise TrainingValidationError("反馈记录不存在")

        self._permissions.require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._feedback.delete(entry)
        self._audits.record(
            event_type="evaluation.feedback.deleted",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "feedback_id": feedback_id,
            },
        )

    def export_feedback(
        self,
        *,
        job_id: int,
        current_user: User,
        fmt: str,
        status: EvaluationFeedbackStatus | None = None,
        kind: EvaluationFeedbackKind | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")

        self._require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
        )

        entries = self.list_feedback(
            job_id,
            current_user=current_user,
            status=status,
            kind=kind,
            tag=tag,
        )

        export_format = fmt.lower()
        if export_format not in {"markdown", "json"}:
            raise TrainingValidationError("不支持的导出格式")

        target_dir = self._knowledge_directory(job.workspace_id, job.project_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"feedback-job-{job.id}-{timestamp}.{ 'md' if export_format == 'markdown' else 'json'}"
        output_path = target_dir / filename

        if export_format == "json":
            payload = [
                {
                    "id": entry.id,
                    "workspace_id": entry.workspace_id,
                    "project_id": entry.project_id,
                    "evaluation_job_id": entry.evaluation_job_id,
                    "training_run_id": entry.training_run_id,
                    "kind": entry.kind.value,
                    "status": entry.status.value,
                    "body": entry.body,
                    "tags": entry.tags,
                    "metric_name": entry.metric_name,
                    "metric_value": entry.metric_value,
                    "created_by": entry.created_by,
                    "created_at": entry.created_at.isoformat(),
                    "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
                }
                for entry in entries
            ]
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            lines: list[str] = [
                f"# 评估反馈导出 - 任务 #{job.id}",
                "",
                f"- 工作空间：{job.workspace_id}",
                f"- 项目：{job.project_id if job.project_id else 'general'}",
                f"- 导出时间：{datetime.utcnow().isoformat()}Z",
                f"- 反馈数量：{len(entries)}",
                "",
            ]
            for entry in entries:
                lines.append(f"## 条目 #{entry.id} ({entry.kind.value})")
                lines.append(f"- 状态：{entry.status.value}")
                if entry.tags:
                    lines.append(f"- 标签：{', '.join(entry.tags)}")
                if entry.metric_name:
                    metric_line = f"- 指标：{entry.metric_name}"
                    if entry.metric_value is not None:
                        metric_line += f" = {entry.metric_value}"
                    lines.append(metric_line)
                if entry.training_run_id:
                    lines.append(f"- 关联训练运行：#{entry.training_run_id}")
                lines.append(f"- 创建人：#{entry.created_by}")
                lines.append(f"- 创建时间：{entry.created_at.isoformat()}")
                if entry.resolved_at:
                    lines.append(f"- 解决时间：{entry.resolved_at.isoformat()}")
                lines.append("")
                lines.append(entry.body)
                lines.append("")
            output_path.write_text("\n".join(lines), encoding="utf-8")

        relative_path = str(output_path.relative_to(self._storage_root()))
        self._audits.record(
            event_type="evaluation.feedback.exported",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "format": export_format,
                "path": relative_path,
                "count": len(entries),
            },
        )

        return {"path": relative_path, "format": export_format, "count": len(entries)}

    def list_feedback_summaries(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        current_user: User,
        limit: int = 20,
    ) -> dict[str, Any]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_operation(
            workspace_id=workspace.id,
            user=current_user,
            operation=RoleOperation.TRAINING_LAUNCH,
        )
        entries = self._feedback.list_open_for_project(
            workspace_id=workspace.id,
            project_id=project_id,
            limit=limit,
            kind=EvaluationFeedbackKind.TODO,
        )
        items = [
            {
                "id": entry.id,
                "evaluation_job_id": entry.evaluation_job_id,
                "training_run_id": entry.training_run_id,
                "kind": entry.kind.value,
                "status": entry.status.value,
                "body": entry.body,
                "tags": entry.tags,
                "metric_name": entry.metric_name,
                "metric_value": entry.metric_value,
                "created_by": entry.created_by,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ]
        return {
            "workspace_id": workspace.id,
            "project_id": project_id,
            "items": items,
        }

    def export_job_report(
        self,
        job_id: int,
        *,
        current_user: User,
    ) -> Path:
        job = self.get_job(job_id, current_user=current_user)
        if not job.report_path:
            raise TrainingValidationError("评估任务尚未生成报告")
        path = self._storage_root() / job.report_path
        if not path.exists():
            raise TrainingValidationError("评估报告文件不存在")
        return path

    def get_report_payload(
        self,
        job_id: int,
        *,
        current_user: User | None,
        from_share_link: bool = False,
    ) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")
        if not from_share_link:
            self._require_operation(
                workspace_id=job.workspace_id,
                user=current_user,
                operation=RoleOperation.EVALUATION_VIEW,
            )

        metrics = job.metrics_json or {}
        cases = self._load_case_studies(job)
        report_markdown = self._read_report_markdown(job)

        training_context = self._build_training_context(job)
        dataset_context = self._build_dataset_context(job)
        artifacts = self._build_report_artifacts(job)

        report_html = self._render_markdown_as_html(report_markdown)

        payload: dict[str, Any] = {
            "job": {
                "id": job.id,
                "workspace_id": job.workspace_id,
                "project_id": job.project_id,
                "training_run_id": job.training_run_id,
                "status": job.status.value,
                "trigger_mode": job.trigger_mode.value,
                "created_at": job.created_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            },
            "metrics": metrics,
            "cases": cases,
            "artifacts": artifacts,
            "training": training_context,
            "dataset": dataset_context,
            "report_markdown": report_markdown,
            "report_html": report_html,
        }
        if from_share_link:
            self._audits.record(
                event_type="evaluation.report.share_accessed",
                user_id=None,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": job.workspace_id,
                    "evaluation_job_id": job.id,
                },
            )
        return payload

    def create_share_token(self, *, job_id: int, current_user: User) -> tuple[str, datetime]:
        job = self._jobs.get(job_id)
        if job is None:
            raise TrainingValidationError("评估任务不存在")
        self._require_operation(
            workspace_id=job.workspace_id,
            user=current_user,
            operation=RoleOperation.EVALUATION_VIEW,
        )

        expires_at = datetime.utcnow() + timedelta(seconds=self.SHARE_TOKEN_TTL_SECONDS)
        payload = {
            "sub": str(job.id),
            "workspace_id": job.workspace_id,
            "aud": self.SHARE_TOKEN_AUDIENCE,
            "exp": expires_at,
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        self._audits.record(
            event_type="evaluation.report.share_created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "expires_at": expires_at.isoformat(),
            },
        )
        return token, expires_at

    def resolve_shared_report_token(self, token: str) -> int:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                audience=self.SHARE_TOKEN_AUDIENCE,
            )
        except ExpiredSignatureError as exc:  # pragma: no cover - defensive branch
            raise TrainingValidationError("分享链接已失效，请重新生成。") from exc
        except JWTError as exc:  # pragma: no cover - defensive branch
            raise TrainingValidationError("分享链接无效或已被篡改。") from exc
        job_id = payload.get("sub")
        try:
            job_id_int = int(job_id)
        except (TypeError, ValueError):  # pragma: no cover - defensive branch
            raise TrainingValidationError("分享链接无效。")
        return job_id_int

    def record_report_export(self, *, job: EvaluationJob, fmt: str, user: User) -> None:
        """记录导出操作用于审计。"""
        self._audits.record(
            event_type="evaluation.report.exported",
            user_id=user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": job.workspace_id,
                "evaluation_job_id": job.id,
                "format": fmt.lower(),
            },
        )

    def generate_pdf_report(self, job: EvaluationJob, report_payload: dict[str, Any]) -> bytes:
        lines: list[str] = [self.PDF_TITLE, ""]
        lines.append(f"Workspace ID: {job.workspace_id}")
        if job.training_run_id:
            lines.append(f"Training Run: #{job.training_run_id}")
        lines.append(f"Generated At: {datetime.utcnow().isoformat()}Z")
        lines.append("")

        metrics = report_payload.get("metrics", {})
        lines.append("Key Metrics:")
        for key, value in metrics.items():
            if key in {"thresholds", "baseline", "delta", "generated_at"}:
                continue
            lines.append(f"  - {key}: {value}")
        lines.append("")

        thresholds = metrics.get("thresholds", {}) or {}
        if thresholds:
            lines.append("Threshold Checks:")
            for name, info in thresholds.items():
                threshold_value = info.get("threshold")
                status = "Triggered" if info.get("triggered") else "OK"
                lines.append(f"  - {name}: threshold {threshold_value} ({status})")
            lines.append("")

        cases = report_payload.get("cases", {}) or {}
        for section, title in (("improved", "Improved Samples"), ("regressed", "Regressed Samples")):
            items = cases.get(section) or []
            if not items:
                continue
            lines.append(title + ":")
            for case in items[:5]:
                reference = case.get("reference", "")
                prediction = case.get("prediction", "")
                score = case.get("score")
                lines.append(f"  - Reference: {reference}")
                lines.append(f"    Prediction: {prediction}")
                if score is not None:
                    lines.append(f"    Match Score: {score}")
            lines.append("")

        content_lines = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]

        def escape(line: str) -> str:
            return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        for line in lines:
            escaped_line = escape(line)
            content_lines.append(f"({escaped_line}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        content_stream = "\n".join(content_lines)
        content_bytes = content_stream.encode("latin-1", "replace")

        pdf = bytearray()

        def write(data: str | bytes) -> None:
            if isinstance(data, bytes):
                pdf.extend(data)
            else:
                pdf.extend(data.encode("latin-1"))

        offsets: list[int] = []

        write("%PDF-1.4\n")

        def add_object(obj: str) -> None:
            offsets.append(len(pdf))
            write(obj)
            if not obj.endswith("\n"):
                write("\n")

        add_object("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        add_object("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        add_object(
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        )
        add_object(
            f"4 0 obj << /Length {len(content_bytes)} >> stream\n{content_stream}\nendstream endobj\n"
        )
        add_object("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

        xref_offset = len(pdf)
        write("xref\n0 6\n0000000000 65535 f \n")
        for offset in offsets:
            write(f"{offset:010} 00000 n \n")
        write("trailer << /Size 6 /Root 1 0 R >>\nstartxref\n")
        write(str(xref_offset))
        write("\n%%EOF\n")

        return bytes(pdf)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _prepare_artifacts(
        self,
        *,
        job: EvaluationJob,
        dataset_version: DatasetVersion | None,
        dataset_file: UploadedEvaluationDataset | None,
    ) -> None:
        root = self._evaluation_directory(
            workspace_id=job.workspace_id,
            project_id=job.project_id,
            job_id=job.id,
        )
        root.mkdir(parents=True, exist_ok=True)
        input_dir = root / "input"
        input_dir.mkdir(exist_ok=True)

        dataset_path: Path | None = None
        if dataset_file is not None:
            dataset_path = input_dir / dataset_file.filename
            dataset_path.write_bytes(dataset_file.content)
        elif dataset_version is not None:
            base = self._storage_root()
            source_root = base / (dataset_version.location_uri or "")
            if not source_root.exists():
                raise TrainingValidationError("数据版本缺少可用的原始文件")
            dataset_path = input_dir / f"dataset-version-{dataset_version.id}"
            if source_root.is_file():
                shutil.copy2(source_root, dataset_path)
            else:
                if dataset_path.exists():
                    shutil.rmtree(dataset_path)
                shutil.copytree(source_root, dataset_path)

        if dataset_path is None:
            raise TrainingValidationError("评估任务缺少输入数据")

        relative_dataset = str(dataset_path.relative_to(self._storage_root()))
        relative_artifact_root = str(root.relative_to(self._storage_root()))
        self._jobs.update(
            job,
            dataset_path=relative_dataset,
            artifact_path=relative_artifact_root,
        )

    def _artifact_root(self, job: EvaluationJob) -> Path | None:
        if not job.artifact_path:
            return None
        return self._storage_root() / job.artifact_path

    def _load_case_studies(self, job: EvaluationJob) -> dict[str, Any]:
        root = self._artifact_root(job)
        if root is None:
            return {"improved": [], "regressed": []}
        path = root / "cases.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:  # pragma: no cover - defensive fallback
                return {"improved": [], "regressed": []}
        # Fallback: synthesize a simple placeholder from metrics
        metrics = job.metrics_json or {}
        improved_sample = {
            "reference": "报告生成时未捕获样例，稍后可重新运行评估以补充。",
            "prediction": "",
            "score": metrics.get("bleu"),
        }
        return {"improved": [improved_sample], "regressed": []}

    def _read_report_markdown(self, job: EvaluationJob) -> str:
        if not job.report_path:
            return ""
        path = self._storage_root() / job.report_path
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _build_training_context(self, job: EvaluationJob) -> dict[str, Any]:
        if not job.training_run_id:
            return {}
        run = job.training_run or self._runs.get(job.training_run_id)
        if run is None:
            return {}
        training_job = run.job or self._training_jobs.get(run.job_id)
        context: dict[str, Any] = {
            "run": {
                "id": run.id,
                "status": run.status.value,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "artifact_uri": run.artifact_uri,
            }
        }
        if training_job is not None:
            context["job"] = {
                "id": training_job.id,
                "base_model": training_job.base_model,
                "adapter_type": training_job.adapter_type.value,
                "project_id": training_job.project_id,
            }
            project = training_job.project or (
                self._projects.get(training_job.project_id) if training_job.project_id else None
            )
            if project is not None:
                context["project"] = {
                    "id": project.id,
                    "name": project.name,
                }
            dataset_version = training_job.dataset_version or (
                self._versions.get(training_job.dataset_version_id)
                if training_job.dataset_version_id
                else None
            )
            if dataset_version is not None:
                context["dataset_version"] = {
                    "id": dataset_version.id,
                    "version": dataset_version.version,
                }
                dataset = dataset_version.dataset
                if dataset is not None:
                    context["dataset"] = {
                        "id": dataset.id,
                        "name": dataset.name,
                    }
        return context

    def _build_dataset_context(self, job: EvaluationJob) -> dict[str, Any]:
        dataset_version = job.dataset_version
        if dataset_version is None and job.dataset_version_id is not None:
            dataset_version = self._versions.get(job.dataset_version_id)

        if dataset_version is None:
            return {}

        dataset = dataset_version.dataset
        context: dict[str, Any] = {
            "dataset_version": {
                "id": dataset_version.id,
                "version": dataset_version.version,
            }
        }
        if dataset is not None:
            context["dataset"] = {
                "id": dataset.id,
                "name": dataset.name,
                "workspace_id": dataset.workspace_id,
            }
        if dataset_version.location_uri:
            context["location_uri"] = dataset_version.location_uri
        return context

    def _build_report_artifacts(self, job: EvaluationJob) -> dict[str, str]:
        base_endpoint = f"/api/v1/evaluations/jobs/{job.id}/export"
        return {
            "markdown": f"{base_endpoint}?format=markdown",
            "json": f"{base_endpoint}?format=json",
            "pdf": f"{base_endpoint}?format=pdf",
        }

    def _render_markdown_as_html(self, content: str | None) -> str:
        if not content:
            return ""
        blocks: list[str] = []
        for block in content.split("\n\n"):
            text = block.strip()
            if not text:
                continue
            escaped = html.escape(text).replace("\n", "<br/>")
            blocks.append(f"<p>{escaped}</p>")
        return "\n".join(blocks)

    def _evaluation_directory(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        job_id: int,
    ) -> Path:
        base = self._storage_root()
        workspace_segment = str(workspace_id)
        project_segment = str(project_id) if project_id is not None else "general"
        return base / workspace_segment / project_segment / "evaluations" / str(job_id)

    def _knowledge_directory(self, workspace_id: int, project_id: int | None) -> Path:
        base = self._storage_root()
        workspace_segment = str(workspace_id)
        project_segment = str(project_id) if project_id is not None else "general"
        return base / workspace_segment / project_segment / "knowledge" / "feedback"

    def _storage_root(self) -> Path:
        return Path(settings.workspace_storage_root).expanduser()

    def _ensure_workspace(self, workspace_id: int) -> Workspace:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        return workspace

    def _require_operation(
        self,
        *,
        workspace_id: int,
        user: User,
        operation: RoleOperation,
    ) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=operation,
            ip_address=None,
            user_agent=None,
        )


def serialize_evaluation_job(job: EvaluationJob) -> dict[str, Any]:
    """Utility serializer used by API layer."""
    return {
        "id": job.id,
        "workspace_id": job.workspace_id,
        "project_id": job.project_id,
        "training_run_id": job.training_run_id,
        "evaluation_template_id": job.evaluation_template_id,
        "dataset_version_id": job.dataset_version_id,
        "status": job.status.value,
        "metrics": job.metrics_json or {},
        "report_path": job.report_path,
        "artifact_path": job.artifact_path,
        "dataset_path": job.dataset_path,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
        "trigger_mode": job.trigger_mode.value,
    }

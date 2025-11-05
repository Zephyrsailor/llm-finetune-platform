"""Dashboard aggregation service."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlmodel import Session

from app.models import (
    AuditLog,
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetVersion,
    Project,
    ProjectStatus,
    User,
    Workspace,
    WorkspaceMember,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.dataset import DataCleaningJobRepository, DatasetRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import ProjectRepository, WorkspaceRepository
from app.schemas.dashboard import DashboardSummary, MetricPlaceholder, StageStatus, WorkspaceSummary
from app.services.errors import AccessDeniedError, WorkspaceNotFoundError
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation

_AUDIT_SAMPLE_LIMIT = 200


class DashboardService:
    """Aggregate workspace delivery status for dashboard view."""

    def __init__(self, session: Session):
        self._session = session
        self._workspaces = WorkspaceRepository(session)
        self._projects = ProjectRepository(session)
        self._users = UserRepository(session)
        self._audits = AuditLogRepository(session)
        self._datasets = DatasetRepository(session)
        self._jobs = DataCleaningJobRepository(session)
        self._permissions = PermissionService(session)

    def get_summary(
        self,
        *,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
        workspace_id: int | None = None,
    ) -> DashboardSummary:
        """Return summary for one or multiple workspaces the user can access."""
        workspaces: Sequence[Workspace]
        if workspace_id is not None:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None:
                raise WorkspaceNotFoundError("工作空间不存在")
            self._permissions.require_operation(
                workspace_id=workspace.id,
                user=current_user,
                operation=RoleOperation.EVALUATION_VIEW,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            workspaces = (workspace,)
        else:
            accessible = self._workspaces.list_for_user(current_user.id)
            workspaces = tuple(
                workspace
                for workspace in accessible
                if self._can_view_workspace(
                    workspace=workspace,
                    user=current_user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )

        summaries = [
            self._build_workspace_summary(workspace=workspace, current_user=current_user)
            for workspace in workspaces
        ]

        self._audits.record(
            event_type="dashboard.view",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "workspace_scope": [summary.workspace_id for summary in summaries],
            },
        )

        return DashboardSummary(generated_at=datetime.utcnow(), workspaces=summaries)

    def _can_view_workspace(
        self,
        *,
        workspace: Workspace,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> bool:
        try:
            self._permissions.require_operation(
                workspace_id=workspace.id,
                user=user,
                operation=RoleOperation.EVALUATION_VIEW,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return True
        except AccessDeniedError:
            return False

    def _build_workspace_summary(self, *, workspace: Workspace, current_user: User) -> WorkspaceSummary:
        members = list(self._workspaces.list_members(workspace.id))
        owner_email = self._select_owner_email(members)
        projects = list(self._projects.list_for_workspace(workspace.id))
        audit_events = list(self._audits.list_for_workspace(workspace.id, limit=_AUDIT_SAMPLE_LIMIT))

        stages = [
            self._summarize_data_stage(workspace=workspace, owner_email=owner_email),
            self._summarize_training_stage(
                workspace=workspace,
                owner_email=owner_email,
                projects=projects,
                events=audit_events,
            ),
            self._summarize_event_stage(
                stage_key="evaluation",
                stage_label="评估",
                owner_email=owner_email,
                events=audit_events,
            ),
            self._summarize_event_stage(
                stage_key="deployment",
                stage_label="部署",
                owner_email=owner_email,
                events=audit_events,
            ),
        ]

        metrics = self._metric_placeholders()
        return WorkspaceSummary(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            stages=stages,
            metrics=metrics,
        )

    def _summarize_data_stage(self, *, workspace: Workspace, owner_email: str | None) -> StageStatus:
        latest = self._jobs.get_latest_job_for_workspace(workspace.id)
        if latest is None:
            datasets = list(self._datasets.list_for_workspace(workspace.id))
            if datasets:
                most_recent = max(datasets, key=lambda item: item.updated_at)
                responsible = self._resolve_user_email(most_recent.created_by) or owner_email
                return StageStatus(
                    stage="data_ingestion",
                    status="in_progress",
                    responsible=responsible,
                    updated_at=most_recent.updated_at,
                    notes="已创建数据集，等待清洗任务完成或生成新版本。",
                )
            return StageStatus(
                stage="data_ingestion",
                status="not_started",
                responsible=owner_email,
                notes="尚未创建任何数据集或触发清洗任务。",
            )

        job, version, dataset = latest
        responsible = self._resolve_user_email(dataset.created_by) or owner_email

        status_map: dict[DataCleaningJobStatus, str] = {
            DataCleaningJobStatus.COMPLETED: "completed",
            DataCleaningJobStatus.RUNNING: "in_progress",
            DataCleaningJobStatus.PENDING: "in_progress",
            DataCleaningJobStatus.FAILED: "unknown",
        }
        status = status_map.get(job.status, "unknown")

        if job.status == DataCleaningJobStatus.FAILED:
            note = job.error_message or "最近一次数据清洗任务失败，需排查日志。"
        elif job.status in (DataCleaningJobStatus.PENDING, DataCleaningJobStatus.RUNNING):
            note = "数据清洗任务正在运行，完成后将更新指标。"
        else:
            note = f"最近完成的版本：v{version.version}（数据集 {dataset.name}）。"

        return StageStatus(
            stage="data_ingestion",
            status=status,  # type: ignore[arg-type]
            responsible=responsible,
            updated_at=job.updated_at,
            notes=note,
        )

    def _summarize_training_stage(
        self,
        *,
        workspace: Workspace,
        owner_email: str | None,
        projects: Sequence[Project],
        events: Sequence[AuditLog],
    ) -> StageStatus:
        latest_event = self._latest_event(events, prefix="training.")
        if latest_event is not None:
            return self._stage_from_event(
                stage_key="training",
                stage_label="训练",
                event=latest_event,
                fallback_responsible=owner_email,
            )

        active_projects = [project for project in projects if project.status == ProjectStatus.ACTIVE]
        if active_projects:
            updated_at = max(project.updated_at for project in active_projects)
            return StageStatus(
                stage="training",
                status="in_progress",
                responsible=owner_email,
                updated_at=updated_at,
                notes="已创建训练项目，等待训练流水线接入与运行记录。",
            )

        return StageStatus(
            stage="training",
            status="not_started",
            responsible=owner_email,
            notes="尚未创建训练项目或训练日志。",
        )

    def _summarize_event_stage(
        self,
        *,
        stage_key: str,
        stage_label: str,
        owner_email: str | None,
        events: Sequence[AuditLog],
    ) -> StageStatus:
        latest_event = self._latest_event(events, prefix=f"{stage_key}.")
        if latest_event is not None:
            return self._stage_from_event(
                stage_key=stage_key,
                stage_label=stage_label,
                event=latest_event,
                fallback_responsible=owner_email,
            )

        return StageStatus(
            stage=stage_key,
            status="not_started",
            responsible=owner_email,
            notes=f"尚未接入{stage_label}流水线事件，保持占位以供后续扩展。",
        )

    def _latest_event(self, events: Sequence[AuditLog], *, prefix: str) -> AuditLog | None:
        for event in events:
            if event.event_type.startswith(prefix):
                return event
        return None

    def _stage_from_event(
        self,
        *,
        stage_key: str,
        stage_label: str,
        event: AuditLog,
        fallback_responsible: str | None,
    ) -> StageStatus:
        if event.event_type.endswith(".completed"):
            status = "completed"
        elif event.event_type.endswith(".failed"):
            status = "unknown"
        else:
            status = "in_progress"

        payload = event.payload if isinstance(event.payload, dict) else {}
        responsible = payload.get("responsible") or fallback_responsible
        notes = payload.get("notes") or payload.get("message")
        if not notes:
            notes = f"最新{stage_label}事件：{event.event_type}。"

        return StageStatus(
            stage=stage_key,
            status=status,  # type: ignore[arg-type]
            responsible=responsible,
            updated_at=event.created_at,
            notes=notes,
        )

    @staticmethod
    def _select_owner_email(members: Iterable[tuple[WorkspaceMember, User]]) -> str | None:
        owners = [
            user.email
            for member, user in members
            if getattr(member, "role", "") == "owner"
        ]
        if owners:
            return owners[0]
        for _, user in members:
            return user.email
        return None

    def _resolve_user_email(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        user = self._users.get_by_id(user_id)
        return user.email if user is not None else None

    @staticmethod
    def _metric_placeholders() -> list[MetricPlaceholder]:
        return [
            MetricPlaceholder(
                key="planned_data_volume",
                label="数据量（条）",
                description="待集成：数据导入完成后展示最近一次导入的记录数。",
                value=None,
                unit="rows",
            ),
            MetricPlaceholder(
                key="latest_training_epoch",
                label="最近训练轮次",
                description="待集成：训练流水线上线后展示最近一次训练的 epoch 数。",
                value=None,
            ),
            MetricPlaceholder(
                key="latest_evaluation_score",
                label="最近评估得分",
                description="待集成：评估模块上线后展示最近一次评估的关键指标。",
                value=None,
            ),
            MetricPlaceholder(
                key="active_deployments",
                label="活跃部署数",
                description="待集成：部署模块上线后展示当前活跃部署数量。",
                value=None,
            ),
        ]

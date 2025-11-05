"""Governance services providing kanban board orchestration."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlmodel import Session

from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalTaskStatus,
    Comment,
    CommentEntityType,
    Dataset,
    DatasetVersion,
    DatasetVersionStatus,
    Deployment,
    DeploymentStatus,
    EvaluationJob,
    EvaluationJobStatus,
    EvaluationTemplate,
    KanbanCard,
    KanbanEntityType,
    KanbanStage,
    KanbanStatus,
    TrainingJob,
    TrainingJobStatus,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.governance import (
    KanbanCardRepository,
    CommentRepository,
    ApprovalRequestRepository,
    ApprovalTaskRepository,
)
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import AccessDeniedError
from app.services.notification import NotificationService
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


def _load_user_map(session: Session, user_ids: Iterable[int]) -> dict[int, User]:
    """Return mapping of user id to user entity for provided identifiers."""
    ids = {user_id for user_id in user_ids if user_id}
    if not ids:
        return {}
    stmt = select(User).where(User.id.in_(ids))
    result = session.exec(stmt).all()
    mapping: dict[int, User] = {}
    for row in result:
        if isinstance(row, User):
            mapping[row.id] = row
        elif isinstance(row, tuple) and row:
            candidate = row[0]
            if isinstance(candidate, User):
                mapping[candidate.id] = candidate
        else:
            try:
                row_mapping = row._mapping  # type: ignore[attr-defined]
            except AttributeError:
                continue
            candidate = row_mapping.get(User) or row_mapping.get("User") or row_mapping.get("users")
            if isinstance(candidate, User):
                mapping[candidate.id] = candidate
    return mapping


def _resolve_entity_metadata(
    session: Session,
    entity_type: CommentEntityType,
    entity_id: int,
) -> tuple[int, int | None]:
    """Return (workspace_id, project_id) for the given governance entity."""
    if entity_type == CommentEntityType.DATASET_VERSION:
        version = session.get(DatasetVersion, entity_id)
        if version is None:
            raise LookupError("数据集版本不存在")
        dataset = session.get(Dataset, version.dataset_id)
        if dataset is None:
            raise LookupError("数据集不存在")
        return dataset.workspace_id, None
    if entity_type == CommentEntityType.TRAINING_JOB:
        job = session.get(TrainingJob, entity_id)
        if job is None:
            raise LookupError("训练任务不存在")
        return job.workspace_id, job.project_id
    if entity_type == CommentEntityType.EVALUATION_JOB:
        job = session.get(EvaluationJob, entity_id)
        if job is None:
            raise LookupError("评估任务不存在")
        return job.workspace_id, job.project_id
    if entity_type == CommentEntityType.DEPLOYMENT:
        deployment = session.get(Deployment, entity_id)
        if deployment is None:
            raise LookupError("部署记录不存在")
        return deployment.workspace_id, deployment.project_id
    raise LookupError("未知的实体类型")


def _require_any_operation(
    permissions: PermissionService,
    *,
    workspace_id: int,
    user: User,
    operations: tuple[RoleOperation, ...],
) -> None:
    last_error: AccessDeniedError | None = None
    for operation in operations:
        try:
            permissions.require_operation(
                workspace_id=workspace_id,
                user=user,
                operation=operation,
                ip_address=None,
                user_agent=None,
            )
            return
        except AccessDeniedError as exc:  # pragma: no cover - OR evaluation
            last_error = exc
    if last_error is not None:
        raise last_error


class GovernanceKanbanService:
    """Coordinate governance kanban board state and interactions."""

    _STATUS_LABELS: dict[KanbanStatus, str] = {
        KanbanStatus.BACKLOG: "待处理",
        KanbanStatus.IN_PROGRESS: "进行中",
        KanbanStatus.BLOCKED: "阻塞",
        KanbanStatus.DONE: "已完成",
    }

    def __init__(self, session: Session, notification_service: NotificationService | None = None):
        self._session = session
        self._cards = KanbanCardRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)
        self._notifications = notification_service or NotificationService(session)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_board(self, *, workspace_id: int, current_user: User) -> dict[str, Any]:
        """Return kanban board grouped by column."""
        self._require_manage(workspace_id=workspace_id, user=current_user)
        entity_meta = self._sync_workspace_cards(workspace_id)
        cards = self._cards.list_for_workspace(workspace_id)
        assignee_ids = {card.assignee_id for card in cards if card.assignee_id}
        assignees = _load_user_map(self._session, assignee_ids)
        columns = []
        indexed: dict[KanbanStatus, list[dict[str, Any]]] = defaultdict(list)
        for card in cards:
            card_meta = entity_meta.get(card.id, {})
            indexed[card.status].append(self._serialize_card(card, assignees, card_meta))
        for status in (
            KanbanStatus.BACKLOG,
            KanbanStatus.IN_PROGRESS,
            KanbanStatus.BLOCKED,
            KanbanStatus.DONE,
        ):
            columns.append(
                {
                    "status": status,
                    "label": self._STATUS_LABELS[status],
                    "tasks": indexed.get(status, []),
                }
            )
        return {
            "workspace_id": workspace_id,
            "generated_at": datetime.utcnow(),
            "columns": columns,
        }

    def create_manual_card(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        stage: KanbanStage,
        status: KanbanStatus,
        title: str,
        description: str | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> KanbanCard:
        """Create a standalone kanban card not bound to domain entities."""
        self._require_manage(workspace_id=workspace_id, user=current_user)
        order_index = self._cards.next_order_index(
            workspace_id=workspace_id,
            stage=stage,
            status=status,
        )
        card = self._cards.create(
            workspace_id=workspace_id,
            project_id=project_id,
            stage=stage,
            status=status,
            title=title,
            description=description,
            entity_type=KanbanEntityType.GENERIC,
            entity_id=None,
            order_index=order_index,
            created_by=current_user.id,
        )
        self._session.commit()
        self._audits.record(
            event_type="governance.kanban.card_created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "card_id": card.id,
                "stage": stage.value,
                "status": status.value,
            },
        )
        return card

    def update_card(
        self,
        *,
        card: KanbanCard,
        title: str | None,
        description: str | None,
        assignee_id: int | None,
        due_at: datetime | None,
        reminder_minutes_before: int | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> KanbanCard:
        """Update assignment and scheduling metadata for a kanban card."""
        self._require_manage(workspace_id=card.workspace_id, user=current_user)
        changed_fields: dict[str, Any] = {}
        if title is not None and title != card.title:
            card.title = title
            changed_fields["title"] = title
        if description is not None and description != card.description:
            card.description = description
            changed_fields["description"] = description
        if assignee_id != card.assignee_id:
            card.assignee_id = assignee_id
            changed_fields["assignee_id"] = assignee_id
        if due_at != card.due_at:
            card.due_at = due_at
            changed_fields["due_at"] = due_at.isoformat() if due_at else None
        if reminder_minutes_before != card.reminder_minutes_before:
            card.reminder_minutes_before = reminder_minutes_before
            card.reminder_sent_at = None
            changed_fields["reminder_minutes_before"] = reminder_minutes_before
        card.updated_by = current_user.id
        if changed_fields:
            self._cards.save(card)
            self._session.commit()
            self._audits.record(
                event_type="governance.kanban.card_updated",
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={
                    "workspace_id": card.workspace_id,
                    "card_id": card.id,
                    "changes": changed_fields,
                },
            )
            if due_at and reminder_minutes_before:
                self._emit_notification_stub(
                    workspace_id=card.workspace_id,
                    card_id=card.id,
                    assignee_id=assignee_id,
                    due_at=due_at,
                    reminder_minutes_before=reminder_minutes_before,
                )
        return card

    def reorder_cards(
        self,
        *,
        workspace_id: int,
        moves: Iterable[dict[str, Any]],
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Persist drag-and-drop ordering updates."""
        self._require_manage(workspace_id=workspace_id, user=current_user)
        updated_cards: list[KanbanCard] = []
        for move in moves:
            card = self._cards.get(int(move["card_id"]))
            if card is None or card.workspace_id != workspace_id:
                continue
            status = move.get("status")
            if isinstance(status, KanbanStatus) and card.status != status:
                card.status = status
            elif isinstance(status, str):
                status_enum = KanbanStatus(status)
                if card.status != status_enum:
                    card.status = status_enum
            stage_value = move.get("stage")
            if stage_value is not None:
                stage_enum = stage_value if isinstance(stage_value, KanbanStage) else KanbanStage(stage_value)
                if card.stage != stage_enum:
                    card.stage = stage_enum
            order_index = float(move.get("order_index", card.order_index))
            if card.order_index != order_index:
                card.order_index = order_index
            card.updated_by = current_user.id
            card.updated_at = datetime.utcnow()
            updated_cards.append(card)
        if not updated_cards:
            return
        self._cards.bulk_update(cards=updated_cards, updated_by=current_user.id)
        self._session.commit()
        self._audits.record(
            event_type="governance.kanban.cards_reordered",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "card_ids": [card.id for card in updated_cards],
            },
        )

    def get_card(self, card_id: int) -> KanbanCard | None:
        """Fetch card by identifier."""
        return self._cards.get(card_id)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sync_workspace_cards(self, workspace_id: int) -> dict[int, dict[str, Any]]:
        """Ensure cards exist for domain entities and reflect latest status."""
        meta: dict[int, dict[str, Any]] = {}
        dirty_cards: list[KanbanCard] = []
        created = False

        def _stage_status_update(
            card: KanbanCard,
            *,
            stage: KanbanStage,
            status: KanbanStatus,
            title: str,
            description: str | None,
            project_id: int | None,
            status_label: str,
            reference: str,
        ) -> None:
            changed = False
            if card.stage != stage:
                card.stage = stage
                changed = True
            if card.status != status:
                card.status = status
                changed = True
            if card.title != title:
                card.title = title
                changed = True
            if description != card.description:
                card.description = description
                changed = True
            if project_id != card.project_id:
                card.project_id = project_id
                changed = True
            if changed:
                dirty_cards.append(card)
            meta[card.id] = {"status_label": status_label, "reference": reference}

        # Dataset versions
        dataset_stmt = (
            select(DatasetVersion, Dataset)
            .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
            .where(Dataset.workspace_id == workspace_id)
        )
        for version, dataset in self._session.exec(dataset_stmt).tuples():
            status = self._map_dataset_status(version.status)
            title = f"数据集 {dataset.name} · v{version.version}"
            description = f"清洗状态：{version.status.value}"
            card = self._cards.get_by_entity(
                workspace_id=workspace_id,
                entity_type=KanbanEntityType.DATASET_VERSION,
                entity_id=version.id,
            )
            if card is None:
                order_index = self._cards.next_order_index(
                    workspace_id=workspace_id,
                    stage=KanbanStage.DATA,
                    status=status,
                )
                card = self._cards.create(
                    workspace_id=workspace_id,
                    project_id=None,
                    stage=KanbanStage.DATA,
                    status=status,
                    title=title,
                    description=description,
                    entity_type=KanbanEntityType.DATASET_VERSION,
                    entity_id=version.id,
                    order_index=order_index,
                    created_by=None,
                )
                created = True
            _stage_status_update(
                card,
                stage=KanbanStage.DATA,
                status=status,
                title=title,
                description=description,
                project_id=None,
                status_label=version.status.value,
                reference=f"dataset_version:{version.id}",
            )

        # Training jobs
        training_stmt = select(TrainingJob).where(TrainingJob.workspace_id == workspace_id)
        for job in self._session.exec(training_stmt).scalars():
            status = self._map_training_status(job.status)
            title = f"训练任务 #{job.id}"
            description = f"模型：{job.base_model}"
            card = self._cards.get_by_entity(
                workspace_id=workspace_id,
                entity_type=KanbanEntityType.TRAINING_JOB,
                entity_id=job.id,
            )
            if card is None:
                order_index = self._cards.next_order_index(
                    workspace_id=workspace_id,
                    stage=KanbanStage.TRAINING,
                    status=status,
                )
                card = self._cards.create(
                    workspace_id=workspace_id,
                    project_id=job.project_id,
                    stage=KanbanStage.TRAINING,
                    status=status,
                    title=title,
                    description=description,
                    entity_type=KanbanEntityType.TRAINING_JOB,
                    entity_id=job.id,
                    order_index=order_index,
                    created_by=None,
                )
                created = True
            _stage_status_update(
                card,
                stage=KanbanStage.TRAINING,
                status=status,
                title=title,
                description=description,
                project_id=job.project_id,
                status_label=job.status.value,
                reference=f"training_job:{job.id}",
            )

        # Evaluation jobs
        eval_stmt = (
            select(EvaluationJob, EvaluationTemplate)
            .join(EvaluationTemplate, EvaluationTemplate.id == EvaluationJob.evaluation_template_id)
            .where(EvaluationJob.workspace_id == workspace_id)
        )
        for job, template in self._session.exec(eval_stmt).tuples():
            status = self._map_evaluation_status(job.status)
            title = f"评估 #{job.id}"
            description = f"模板：{template.name}"
            card = self._cards.get_by_entity(
                workspace_id=workspace_id,
                entity_type=KanbanEntityType.EVALUATION_JOB,
                entity_id=job.id,
            )
            if card is None:
                order_index = self._cards.next_order_index(
                    workspace_id=workspace_id,
                    stage=KanbanStage.EVALUATION,
                    status=status,
                )
                card = self._cards.create(
                    workspace_id=workspace_id,
                    project_id=job.project_id,
                    stage=KanbanStage.EVALUATION,
                    status=status,
                    title=title,
                    description=description,
                    entity_type=KanbanEntityType.EVALUATION_JOB,
                    entity_id=job.id,
                    order_index=order_index,
                    created_by=None,
                )
                created = True
            _stage_status_update(
                card,
                stage=KanbanStage.EVALUATION,
                status=status,
                title=title,
                description=description,
                project_id=job.project_id,
                status_label=job.status.value,
                reference=f"evaluation_job:{job.id}",
            )

        # Deployments
        deployment_stmt = select(Deployment).where(Deployment.workspace_id == workspace_id)
        for deployment in self._session.exec(deployment_stmt).scalars():
            status = self._map_deployment_status(deployment.status)
            title = f"部署 #{deployment.id}"
            description = (
                f"环境：{deployment.environment}"
                if deployment.environment
                else "部署任务"
            )
            card = self._cards.get_by_entity(
                workspace_id=workspace_id,
                entity_type=KanbanEntityType.DEPLOYMENT,
                entity_id=deployment.id,
            )
            if card is None:
                order_index = self._cards.next_order_index(
                    workspace_id=workspace_id,
                    stage=KanbanStage.DEPLOYMENT,
                    status=status,
                )
                card = self._cards.create(
                    workspace_id=workspace_id,
                    project_id=deployment.project_id,
                    stage=KanbanStage.DEPLOYMENT,
                    status=status,
                    title=title,
                    description=description,
                    entity_type=KanbanEntityType.DEPLOYMENT,
                    entity_id=deployment.id,
                    order_index=order_index,
                    created_by=None,
                )
                created = True
            _stage_status_update(
                card,
                stage=KanbanStage.DEPLOYMENT,
                status=status,
                title=title,
                description=description,
                project_id=deployment.project_id,
                status_label=deployment.status.value,
                reference=f"deployment:{deployment.id}",
            )

        if dirty_cards:
            self._cards.bulk_update(cards=dirty_cards, updated_by=None)
        if created or dirty_cards:
            self._session.commit()
        return meta

    def _map_dataset_status(self, status: DatasetVersionStatus) -> KanbanStatus:
        if status == DatasetVersionStatus.COMPLETED:
            return KanbanStatus.DONE
        if status == DatasetVersionStatus.PROCESSING:
            return KanbanStatus.IN_PROGRESS
        if status == DatasetVersionStatus.FAILED:
            return KanbanStatus.BLOCKED
        return KanbanStatus.BACKLOG

    def _map_training_status(self, status: TrainingJobStatus) -> KanbanStatus:
        if status in (TrainingJobStatus.PENDING, TrainingJobStatus.QUEUED):
            return KanbanStatus.BACKLOG
        if status == TrainingJobStatus.RUNNING:
            return KanbanStatus.IN_PROGRESS
        if status == TrainingJobStatus.COMPLETED:
            return KanbanStatus.DONE
        if status in (TrainingJobStatus.FAILED, TrainingJobStatus.CANCELED):
            return KanbanStatus.BLOCKED
        return KanbanStatus.BACKLOG

    def _map_evaluation_status(self, status: EvaluationJobStatus) -> KanbanStatus:
        if status == EvaluationJobStatus.PENDING:
            return KanbanStatus.BACKLOG
        if status == EvaluationJobStatus.RUNNING:
            return KanbanStatus.IN_PROGRESS
        if status == EvaluationJobStatus.COMPLETED:
            return KanbanStatus.DONE
        if status == EvaluationJobStatus.FAILED:
            return KanbanStatus.BLOCKED
        return KanbanStatus.BACKLOG

    def _map_deployment_status(self, status: DeploymentStatus) -> KanbanStatus:
        if status == DeploymentStatus.ACTIVE:
            return KanbanStatus.DONE
        if status in (DeploymentStatus.PENDING, DeploymentStatus.ROLLED_BACK):
            return KanbanStatus.BACKLOG
        if status == DeploymentStatus.DEPLOYING:
            return KanbanStatus.IN_PROGRESS
        if status == DeploymentStatus.FAILED:
            return KanbanStatus.BLOCKED
        return KanbanStatus.BACKLOG

    def _serialize_card(
        self,
        card: KanbanCard,
        assignees: dict[int, User],
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        linked = None
        if card.entity_type != KanbanEntityType.GENERIC:
            linked = {
                "type": card.entity_type,
                "id": card.entity_id,
                "status": meta.get("status_label"),
                "reference": meta.get("reference"),
            }
        assignee_payload = None
        if card.assignee_id and card.assignee_id in assignees:
            user = assignees[card.assignee_id]
            assignee_payload = {"id": user.id, "email": user.email}
        return {
            "id": card.id,
            "stage": card.stage,
            "status": card.status,
            "title": card.title,
            "description": card.description,
            "order_index": card.order_index,
            "due_at": card.due_at,
            "reminder_minutes_before": card.reminder_minutes_before,
            "assignee": assignee_payload,
            "linked_entity": linked,
            "updated_at": card.updated_at,
        }

    def _emit_notification_stub(
        self,
        *,
        workspace_id: int,
        card_id: int,
        assignee_id: int | None,
        due_at: datetime,
        reminder_minutes_before: int,
    ) -> None:
        """Stub for notification integration used by later stories."""
        self._audits.record(
            event_type="governance.notification.queued",
            user_id=assignee_id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace_id,
                "card_id": card_id,
                "due_at": due_at.isoformat(),
                "reminder_minutes_before": reminder_minutes_before,
            },
        )
        self._notifications.enqueue_event(
            workspace_id=workspace_id,
            project_id=None,
            event_type="governance.kanban.reminder",
            payload={
                "card_id": card_id,
                "assignee_id": assignee_id,
                "due_at": due_at.isoformat(),
                "reminder_minutes_before": reminder_minutes_before,
            },
        )

    def _require_manage(self, *, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )


class GovernanceCommentService:
    """Handle collaborative comments on governance-managed entities."""

    _ENTITY_OPERATIONS: dict[CommentEntityType, tuple[RoleOperation, ...]] = {
        CommentEntityType.DATASET_VERSION: (RoleOperation.DATA_IMPORT, RoleOperation.APPROVAL_MANAGE),
        CommentEntityType.TRAINING_JOB: (RoleOperation.TRAINING_LAUNCH, RoleOperation.APPROVAL_MANAGE),
        CommentEntityType.EVALUATION_JOB: (RoleOperation.EVALUATION_VIEW, RoleOperation.APPROVAL_MANAGE),
        CommentEntityType.DEPLOYMENT: (RoleOperation.DEPLOYMENT_MANAGE, RoleOperation.APPROVAL_MANAGE),
    }

    def __init__(
        self,
        session: Session,
        notification_service: NotificationService | None = None,
    ):
        self._session = session
        self._comments = CommentRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)
        self._notifications = notification_service or NotificationService(session)

    def list_comments(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
        current_user: User,
    ) -> list[dict[str, Any]]:
        operations = self._ENTITY_OPERATIONS.get(entity_type)
        if operations is None:
            raise LookupError("未知的实体类型")
        _require_any_operation(
            self._permissions,
            workspace_id=workspace_id,
            user=current_user,
            operations=operations,
        )
        comments = self._comments.list_for_entity(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        user_ids: set[int] = set()
        for comment in comments:
            user_ids.add(comment.created_by)
            user_ids.update(comment.mentions)
        user_map = _load_user_map(self._session, user_ids)
        return [self._serialize_comment(comment, user_map) for comment in comments]

    def create_comment(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
        body: str,
        mentions: list[int],
        attachments: list[dict],
        context: str | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        operations = self._ENTITY_OPERATIONS.get(entity_type)
        if operations is None:
            raise LookupError("未知的实体类型")
        _require_any_operation(
            self._permissions,
            workspace_id=workspace_id,
            user=current_user,
            operations=operations,
        )
        entity_workspace_id, project_id = _resolve_entity_metadata(self._session, entity_type, entity_id)
        if entity_workspace_id != workspace_id:
            raise AccessDeniedError("目标实体不属于该工作空间。")
        mention_ids = [
            user_id
            for user_id in mentions
            if self._workspaces.is_member(workspace_id=workspace_id, user_id=user_id)
        ]
        normalized_attachments = [self._normalize_attachment(item) for item in attachments]
        comment = self._comments.create(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            body=body,
            mentions=mention_ids,
            attachments=normalized_attachments,
            context=context,
            created_by=current_user.id,
        )
        self._session.commit()
        self._audits.record(
            event_type="governance.comment.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "comment_id": comment.id,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "mentions": mention_ids,
            },
        )
        for recipient_id in mention_ids:
            self._audits.record(
                event_type="governance.notification.queued",
                user_id=recipient_id,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": workspace_id,
                    "comment_id": comment.id,
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                },
            )
        self._notifications.enqueue_event(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type="governance.comment.created",
            payload={
                "comment_id": comment.id,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "mentions": mention_ids,
                "author_id": current_user.id,
            },
            actor_id=current_user.id,
        )
        if mention_ids:
            self._notifications.enqueue_event(
                workspace_id=workspace_id,
                project_id=project_id,
                event_type="governance.comment.mention",
                payload={
                    "comment_id": comment.id,
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                    "target_user_ids": mention_ids,
                },
                actor_id=current_user.id,
            )
        user_ids = set(mention_ids)
        user_ids.add(comment.created_by)
        user_map = _load_user_map(self._session, user_ids)
        return self._serialize_comment(comment, user_map)

    @staticmethod
    def _normalize_attachment(payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("附件名称不能为空")
        url = payload.get("url")
        if url is not None:
            url = str(url)
        return {"name": name, "url": url}

    def _serialize_comment(self, comment: Comment, users: dict[int, User]) -> dict[str, Any]:
        author = users.get(comment.created_by)
        author_payload = {"id": author.id, "email": author.email} if author else {"id": comment.created_by}
        mention_payload = []
        for user_id in comment.mentions:
            user = users.get(user_id)
            if user:
                mention_payload.append({"id": user.id, "email": user.email})
            else:
                mention_payload.append({"id": user_id})
        return {
            "id": comment.id,
            "workspace_id": comment.workspace_id,
            "entity_type": comment.entity_type,
            "entity_id": comment.entity_id,
            "body": comment.body,
            "mentions": mention_payload,
            "attachments": comment.attachments,
            "context": comment.context,
            "author": author_payload,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
        }


class GovernanceApprovalService:
    """Manage approval workflows for governance entities."""

    _ENTITY_OPERATIONS: dict[CommentEntityType, tuple[RoleOperation, ...]] = GovernanceCommentService._ENTITY_OPERATIONS

    def __init__(self, session: Session, notification_service: NotificationService | None = None):
        self._session = session
        self._requests = ApprovalRequestRepository(session)
        self._tasks = ApprovalTaskRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)
        self._notifications = notification_service or NotificationService(session)

    def list_requests(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
        current_user: User,
    ) -> list[dict[str, Any]]:
        operations = self._ENTITY_OPERATIONS.get(entity_type)
        if operations is None:
            raise LookupError("未知的实体类型")
        privileged = self._has_manage_access(workspace_id=workspace_id, user=current_user)
        if not privileged:
            _require_any_operation(
                self._permissions,
                workspace_id=workspace_id,
                user=current_user,
                operations=operations,
            )
        requests = list(
            self._requests.list_for_entity(
                workspace_id=workspace_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        task_cache: dict[int, list[ApprovalTask]] = {
            request.id: list(self._tasks.list_for_request(request.id))
            for request in requests
        }
        if not privileged:
            filtered: list[ApprovalRequest] = []
            for request in requests:
                tasks = task_cache.get(request.id, [])
                if request.requested_by == current_user.id or any(task.approver_id == current_user.id for task in tasks):
                    filtered.append(request)
            requests = filtered
        user_ids: set[int] = set()
        for request in requests:
            user_ids.add(request.requested_by)
            for task in task_cache.get(request.id, []):
                user_ids.add(task.approver_id)
                if task.decided_by:
                    user_ids.add(task.decided_by)
        user_map = _load_user_map(self._session, user_ids)
        return [
            self._serialize_request(request, task_cache.get(request.id, []), user_map)
            for request in requests
        ]

    def create_request(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
        title: str,
        description: str | None,
        approver_ids: list[int],
        due_at: datetime | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        if not approver_ids:
            raise ValueError("审批人列表不能为空")
        self._require_manage(workspace_id=workspace_id, user=current_user)
        entity_workspace_id, project_id = _resolve_entity_metadata(self._session, entity_type, entity_id)
        if entity_workspace_id != workspace_id:
            raise AccessDeniedError("目标实体不属于该工作空间。")
        unique_approvers = []
        for approver_id in approver_ids:
            if approver_id not in unique_approvers and self._workspaces.is_member(workspace_id, approver_id):
                unique_approvers.append(approver_id)
        if not unique_approvers:
            raise ValueError("审批人列表不能为空")
        request = self._requests.create(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            description=description,
            requested_by=current_user.id,
            due_at=due_at,
        )
        for approver_id in unique_approvers:
            self._tasks.create(request_id=request.id, approver_id=approver_id)
        self._session.commit()
        self._audits.record(
            event_type="governance.approval.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "request_id": request.id,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "approver_ids": unique_approvers,
            },
        )
        for approver_id in unique_approvers:
            self._audits.record(
                event_type="governance.notification.queued",
                user_id=approver_id,
                ip_address=None,
                user_agent=None,
                payload={
                    "workspace_id": workspace_id,
                    "request_id": request.id,
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                },
            )
        self._notifications.enqueue_event(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type="governance.approval.requested",
            payload={
                "request_id": request.id,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "approver_ids": unique_approvers,
            },
            actor_id=current_user.id,
        )
        tasks = list(self._tasks.list_for_request(request.id))
        user_ids = {request.requested_by}
        for task in tasks:
            user_ids.add(task.approver_id)
        user_map = _load_user_map(self._session, user_ids)
        return self._serialize_request(request, tasks, user_map)

    def record_decision(
        self,
        *,
        request_id: int,
        decision_status: ApprovalTaskStatus,
        notes: str | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        request = self._requests.get(request_id)
        if request is None:
            raise LookupError("审批请求不存在")
        tasks = list(self._tasks.list_for_request(request_id))
        task = next((item for item in tasks if item.approver_id == current_user.id), None)
        if task is None:
            raise AccessDeniedError("当前用户无权处理该审批。")
        if task.status != ApprovalTaskStatus.PENDING:
            raise ValueError("审批任务已处理")
        if decision_status not in (ApprovalTaskStatus.APPROVED, ApprovalTaskStatus.REJECTED):
            raise ValueError("无效的审批状态")
        self._tasks.save(
            task,
            status=decision_status,
            actor_id=current_user.id,
            notes=notes,
        )
        updated_tasks = list(self._tasks.list_for_request(request_id))
        new_status = self._aggregate_status(updated_tasks)
        if new_status != request.status:
            self._requests.save(request, status=new_status)
        else:
            self._requests.save(request)
        self._session.commit()
        self._audits.record(
            event_type="governance.approval.decision",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": request.workspace_id,
                "request_id": request.id,
                "decision": decision_status.value,
                "notes": notes,
            },
        )
        if new_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            self._audits.record(
                event_type="governance.approval.completed",
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={
                    "workspace_id": request.workspace_id,
                    "request_id": request.id,
                    "status": new_status.value,
                },
            )
            self._notifications.enqueue_event(
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                event_type="governance.approval.completed",
                payload={
                    "request_id": request.id,
                    "status": new_status.value,
                },
                actor_id=current_user.id,
            )
        user_ids = {request.requested_by}
        for task_item in updated_tasks:
            user_ids.add(task_item.approver_id)
            if task_item.decided_by:
                user_ids.add(task_item.decided_by)
        user_map = _load_user_map(self._session, user_ids)
        return self._serialize_request(request, updated_tasks, user_map)

    def _has_manage_access(self, *, workspace_id: int, user: User) -> bool:
        try:
            self._require_manage(workspace_id=workspace_id, user=user)
            return True
        except AccessDeniedError:
            return False

    @staticmethod
    def _aggregate_status(tasks: list[ApprovalTask]) -> ApprovalStatus:
        if any(task.status == ApprovalTaskStatus.REJECTED for task in tasks):
            return ApprovalStatus.REJECTED
        if all(task.status == ApprovalTaskStatus.APPROVED for task in tasks):
            return ApprovalStatus.APPROVED
        return ApprovalStatus.PENDING

    def _serialize_request(
        self,
        request: ApprovalRequest,
        tasks: list[ApprovalTask],
        users: dict[int, User],
    ) -> dict[str, Any]:
        requester = users.get(request.requested_by)
        requester_payload = (
            {"id": requester.id, "email": requester.email}
            if requester
            else {"id": request.requested_by}
        )
        task_payloads = []
        for task in tasks:
            approver = users.get(task.approver_id)
            approver_payload = (
                {"id": approver.id, "email": approver.email}
                if approver
                else {"id": task.approver_id}
            )
            decided_by_user = users.get(task.decided_by) if task.decided_by else None
            task_payloads.append(
                {
                    "id": task.id,
                    "approver": approver_payload,
                    "status": task.status,
                    "decided_at": task.decided_at,
                    "decided_by": (
                        {"id": decided_by_user.id, "email": decided_by_user.email}
                        if decided_by_user
                        else ({"id": task.decided_by} if task.decided_by else None)
                    ),
                    "notes": task.notes,
                }
            )
        return {
            "id": request.id,
            "workspace_id": request.workspace_id,
            "entity_type": request.entity_type,
            "entity_id": request.entity_id,
            "title": request.title,
            "description": request.description,
            "status": request.status,
            "due_at": request.due_at,
            "requested_by": requester_payload,
            "tasks": task_payloads,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
        }

    def _require_manage(self, *, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )

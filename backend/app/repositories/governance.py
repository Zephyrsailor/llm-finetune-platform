"""Repositories for governance and collaboration entities."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlmodel import Session

from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalTask,
    ApprovalTaskStatus,
    Comment,
    CommentEntityType,
    KanbanCard,
    KanbanEntityType,
    KanbanStatus,
)


class KanbanCardRepository:
    """Persist and query kanban cards for governance board."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, card_id: int) -> KanbanCard | None:
        return self._session.get(KanbanCard, card_id)

    def get_by_entity(
        self,
        *,
        workspace_id: int,
        entity_type: KanbanEntityType,
        entity_id: int,
    ) -> KanbanCard | None:
        statement = (
            select(KanbanCard)
            .where(
                KanbanCard.workspace_id == workspace_id,
                KanbanCard.entity_type == entity_type,
                KanbanCard.entity_id == entity_id,
            )
            .limit(1)
        )
        return self._session.exec(statement).scalars().first()

    def list_for_workspace(self, workspace_id: int) -> Sequence[KanbanCard]:
        statement = (
            select(KanbanCard)
            .where(KanbanCard.workspace_id == workspace_id)
            .order_by(KanbanCard.stage, KanbanCard.status, KanbanCard.order_index, KanbanCard.id)
        )
        return tuple(self._session.exec(statement).scalars().all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        stage,
        status,
        title: str,
        description: str | None,
        entity_type: KanbanEntityType,
        entity_id: int | None,
        order_index: float,
        created_by: int | None,
    ) -> KanbanCard:
        card = KanbanCard(
            workspace_id=workspace_id,
            project_id=project_id,
            stage=stage,
            status=status,
            title=title,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            order_index=order_index,
            created_by=created_by,
            updated_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._session.add(card)
        self._session.flush()
        self._session.refresh(card)
        return card

    def save(self, card: KanbanCard) -> KanbanCard:
        card.updated_at = datetime.utcnow()
        self._session.add(card)
        self._session.flush()
        self._session.refresh(card)
        return card

    def bulk_update(
        self,
        *,
        cards: Iterable[KanbanCard],
        updated_by: int | None,
    ) -> None:
        current_time = datetime.utcnow()
        for card in cards:
            card.updated_by = updated_by
            card.updated_at = current_time
            self._session.add(card)
        self._session.flush()

    def next_order_index(
        self,
        *,
        workspace_id: int,
        stage,
        status: KanbanStatus,
    ) -> float:
        statement = (
            select(KanbanCard.order_index)
            .where(
                KanbanCard.workspace_id == workspace_id,
                KanbanCard.stage == stage,
                KanbanCard.status == status,
            )
            .order_by(KanbanCard.order_index.desc())
            .limit(1)
        )
        result = self._session.exec(statement).first()
        if isinstance(result, (float, int)):
            return float(result) + 1.0
        if isinstance(result, tuple) and result:
            maybe_value = result[0]
            if isinstance(maybe_value, (float, int)):
                return float(maybe_value) + 1.0
        return 1.0

    @staticmethod
    def _normalize(rows: list) -> list[KanbanCard]:  # pragma: no cover - retained for compatibility
        return rows


class CommentRepository:
    """Data access helpers for governance comments."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_entity(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
    ) -> Sequence[Comment]:
        statement = (
            select(Comment)
            .where(
                Comment.workspace_id == workspace_id,
                Comment.entity_type == entity_type,
                Comment.entity_id == entity_id,
            )
            .order_by(Comment.created_at.asc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        entity_type: CommentEntityType,
        entity_id: int,
        body: str,
        mentions: list[int],
        attachments: list[dict],
        context: str | None,
        created_by: int,
    ) -> Comment:
        comment = Comment(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            body=body,
            mentions=mentions,
            attachments=attachments,
            context=context,
            created_by=created_by,
            updated_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._session.add(comment)
        self._session.flush()
        self._session.refresh(comment)
        return comment

    def save(self, comment: Comment, *, updated_by: int | None) -> Comment:
        comment.updated_by = updated_by
        comment.updated_at = datetime.utcnow()
        self._session.add(comment)
        self._session.flush()
        self._session.refresh(comment)
        return comment


class ApprovalRequestRepository:
    """Persistence helpers for approval workflows."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, request_id: int) -> ApprovalRequest | None:
        return self._session.get(ApprovalRequest, request_id)

    def list_for_entity(
        self,
        *,
        workspace_id: int,
        entity_type: CommentEntityType,
        entity_id: int,
    ) -> Sequence[ApprovalRequest]:
        statement = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.workspace_id == workspace_id,
                ApprovalRequest.entity_type == entity_type,
                ApprovalRequest.entity_id == entity_id,
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        entity_type: CommentEntityType,
        entity_id: int,
        title: str,
        description: str | None,
        requested_by: int,
        due_at: datetime | None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            workspace_id=workspace_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            description=description,
            requested_by=requested_by,
            due_at=due_at,
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._session.add(request)
        self._session.flush()
        self._session.refresh(request)
        return request

    def save(self, request: ApprovalRequest, *, status: ApprovalStatus | None = None) -> ApprovalRequest:
        if status is not None:
            request.status = status
        request.updated_at = datetime.utcnow()
        self._session.add(request)
        self._session.flush()
        self._session.refresh(request)
        return request


class ApprovalTaskRepository:
    """Manage individual approval tasks."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, *, request_id: int, approver_id: int) -> ApprovalTask:
        task = ApprovalTask(
            request_id=request_id,
            approver_id=approver_id,
            status=ApprovalTaskStatus.PENDING,
        )
        self._session.add(task)
        self._session.flush()
        self._session.refresh(task)
        return task

    def list_for_request(self, request_id: int) -> Sequence[ApprovalTask]:
        statement = select(ApprovalTask).where(ApprovalTask.request_id == request_id)
        return tuple(self._session.exec(statement).scalars().all())

    def get_for_request_and_approver(
        self,
        *,
        request_id: int,
        approver_id: int,
    ) -> ApprovalTask | None:
        statement = (
            select(ApprovalTask)
            .where(
                ApprovalTask.request_id == request_id,
                ApprovalTask.approver_id == approver_id,
            )
            .limit(1)
        )
        return self._session.exec(statement).scalars().first()

    def save(
        self,
        task: ApprovalTask,
        *,
        status: ApprovalTaskStatus,
        actor_id: int,
        notes: str | None,
    ) -> ApprovalTask:
        task.status = status
        task.decided_at = datetime.utcnow()
        task.decided_by = actor_id
        task.notes = notes
        self._session.add(task)
        self._session.flush()
        self._session.refresh(task)
        return task

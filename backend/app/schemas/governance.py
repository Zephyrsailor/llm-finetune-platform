"""Pydantic schemas for governance module APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ApprovalStatus,
    ApprovalTaskStatus,
    CommentEntityType,
    KanbanEntityType,
    KanbanStage,
    KanbanStatus,
)


class KanbanLinkedEntityResponse(BaseModel):
    type: KanbanEntityType
    id: int | None = None
    status: str | None = None
    reference: str | None = None


class KanbanAssigneeResponse(BaseModel):
    id: int
    email: str


class KanbanCardResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    stage: KanbanStage
    status: KanbanStatus
    title: str
    description: str | None = None
    order_index: float
    due_at: datetime | None = None
    reminder_minutes_before: int | None = None
    assignee: KanbanAssigneeResponse | None = None
    linked_entity: KanbanLinkedEntityResponse | None = None
    updated_at: datetime


class KanbanColumnResponse(BaseModel):
    status: KanbanStatus
    label: str
    tasks: list[KanbanCardResponse]


class KanbanBoardResponse(BaseModel):
    workspace_id: int
    generated_at: datetime
    columns: list[KanbanColumnResponse]


class KanbanCardCreateRequest(BaseModel):
    workspace_id: int
    project_id: int | None = None
    stage: KanbanStage
    status: KanbanStatus = KanbanStatus.BACKLOG
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class KanbanCardUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    assignee_id: int | None = None
    due_at: datetime | None = None
    reminder_minutes_before: int | None = Field(default=None, ge=5, le=7 * 24 * 60)


class KanbanCardMove(BaseModel):
    card_id: int
    status: KanbanStatus
    order_index: float = Field(ge=0)
    stage: KanbanStage | None = None


class KanbanReorderRequest(BaseModel):
    workspace_id: int
    moves: list[KanbanCardMove]


class CommentAttachment(BaseModel):
    name: str = Field(max_length=200)
    url: str | None = Field(default=None, max_length=2000)


class CommentActorResponse(BaseModel):
    id: int
    email: str | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    workspace_id: int
    entity_type: CommentEntityType
    entity_id: int
    body: str
    mentions: list[CommentActorResponse]
    attachments: list[CommentAttachment]
    context: str | None = None
    author: CommentActorResponse
    created_at: datetime
    updated_at: datetime


class CommentCreateRequest(BaseModel):
    workspace_id: int
    entity_type: CommentEntityType
    entity_id: int
    body: str = Field(max_length=4000)
    mentions: list[int] = Field(default_factory=list)
    attachments: list[CommentAttachment] = Field(default_factory=list)
    context: str | None = Field(default=None, max_length=1024)


class ApprovalTaskResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    approver: CommentActorResponse
    status: ApprovalTaskStatus
    decided_at: datetime | None = None
    decided_by: CommentActorResponse | None = None
    notes: str | None = None


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    workspace_id: int
    entity_type: CommentEntityType
    entity_id: int
    title: str
    description: str | None = None
    status: ApprovalStatus
    due_at: datetime | None = None
    requested_by: CommentActorResponse
    tasks: list[ApprovalTaskResponse]
    created_at: datetime
    updated_at: datetime


class ApprovalCreateRequest(BaseModel):
    workspace_id: int
    entity_type: CommentEntityType
    entity_id: int
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    approver_ids: list[int] = Field(min_length=1)
    due_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    status: ApprovalTaskStatus
    notes: str | None = Field(default=None, max_length=1000)

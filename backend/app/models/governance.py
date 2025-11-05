"""Governance and collaboration domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import Column, Enum, Float, JSON
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from app.models.user import User
from app.models.workspace import Workspace, Project


class KanbanStage(StrEnum):
    """High-level delivery stages represented on the governance board."""

    DATA = "data"
    TRAINING = "training"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"


class KanbanStatus(StrEnum):
    """Board column state for kanban cards."""

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class KanbanEntityType(StrEnum):
    """Supported domain entities that can surface on the kanban board."""

    GENERIC = "generic"
    DATASET_VERSION = "dataset_version"
    TRAINING_JOB = "training_job"
    EVALUATION_JOB = "evaluation_job"
    DEPLOYMENT = "deployment"


class KanbanCard(SQLModel, table=True):
    """Tracked task visible on the governance kanban board."""

    __tablename__ = "kanban_cards"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    stage: KanbanStage = Field(
        default=KanbanStage.DATA,
        sa_column=Column(Enum(KanbanStage, name="kanban_stage_enum"), nullable=False),
    )
    status: KanbanStatus = Field(
        default=KanbanStatus.BACKLOG,
        sa_column=Column(Enum(KanbanStatus, name="kanban_status_enum"), nullable=False),
    )
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    order_index: float = Field(
        sa_column=Column(Float, nullable=False),
        default=1.0,
        description="Ordering value inside a given stage/status column.",
    )
    entity_type: KanbanEntityType = Field(
        default=KanbanEntityType.GENERIC,
        sa_column=Column(Enum(KanbanEntityType, name="kanban_entity_type_enum"), nullable=False),
    )
    entity_id: int | None = Field(default=None, index=True)
    assignee_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    due_at: datetime | None = Field(default=None)
    reminder_minutes_before: int | None = Field(default=None)
    reminder_sent_at: datetime | None = Field(default=None)
    created_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    workspace: Workspace = Relationship(sa_relationship=relationship("Workspace"))
    project: Optional[Project] = Relationship(sa_relationship=relationship("Project"))
    assignee: Optional[User] = Relationship(
        sa_relationship=relationship("User", foreign_keys="[KanbanCard.assignee_id]")
    )
    creator: Optional[User] = Relationship(
        sa_relationship=relationship("User", foreign_keys="[KanbanCard.created_by]")
    )
    updater: Optional[User] = Relationship(
        sa_relationship=relationship("User", foreign_keys="[KanbanCard.updated_by]")
    )


class CommentEntityType(StrEnum):
    """Domain objects that support collaborative comments."""

    DATASET_VERSION = "dataset_version"
    TRAINING_JOB = "training_job"
    EVALUATION_JOB = "evaluation_job"
    DEPLOYMENT = "deployment"


class Comment(SQLModel, table=True):
    """User comment associated with platform entities."""

    __tablename__ = "governance_comments"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    entity_type: CommentEntityType = Field(
        sa_column=Column(Enum(CommentEntityType, name="comment_entity_type_enum"), nullable=False),
    )
    entity_id: int = Field(index=True)
    body: str = Field(max_length=4000)
    mentions: list[int] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    attachments: list[dict] = Field(default_factory=list, sa_column=Column(JSON, default=list))
    context: str | None = Field(default=None, max_length=1024)
    created_by: int = Field(foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class ApprovalStatus(StrEnum):
    """Lifecycle status for approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalTaskStatus(StrEnum):
    """State of each approver's decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(SQLModel, table=True):
    """Approval workflow attached to governance entities."""

    __tablename__ = "approval_requests"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    entity_type: CommentEntityType = Field(
        sa_column=Column(Enum(CommentEntityType, name="comment_entity_type_enum"), nullable=False),
    )
    entity_id: int = Field(index=True)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        sa_column=Column(Enum(ApprovalStatus, name="approval_status_enum"), nullable=False),
    )
    requested_by: int = Field(foreign_key="users.id", index=True)
    due_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class ApprovalTask(SQLModel, table=True):
    """Per-approver decision record for an approval request."""

    __tablename__ = "approval_tasks"

    id: int | None = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="approval_requests.id", index=True)
    approver_id: int = Field(foreign_key="users.id", index=True)
    status: ApprovalTaskStatus = Field(
        default=ApprovalTaskStatus.PENDING,
        sa_column=Column(Enum(ApprovalTaskStatus, name="approval_task_status_enum"), nullable=False),
    )
    decided_at: datetime | None = Field(default=None)
    decided_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    notes: str | None = Field(default=None, max_length=1000)

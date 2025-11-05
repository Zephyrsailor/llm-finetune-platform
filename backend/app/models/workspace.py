"""Workspace and project domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class WorkspaceStatus(StrEnum):
    """Allowed lifecycle states for a workspace."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectStatus(StrEnum):
    """Allowed lifecycle states for a project."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Workspace(SQLModel, table=True):
    """Workspace aggregates multiple projects under a shared access boundary."""

    __tablename__ = "workspaces"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    description: str | None = Field(default=None, max_length=1024)
    plan: str | None = Field(default=None, max_length=64)
    status: WorkspaceStatus = Field(default=WorkspaceStatus.ACTIVE)
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class WorkspaceMember(SQLModel, table=True):
    """Mapping table between workspaces and their members."""

    __tablename__ = "workspace_members"

    workspace_id: int = Field(foreign_key="workspaces.id", primary_key=True)
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    role: str = Field(default="member", max_length=32, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Project(SQLModel, table=True):
    """Project belongs to a workspace and encapsulates ML fine-tune artefacts."""

    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=1024)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

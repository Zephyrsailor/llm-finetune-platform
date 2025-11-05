"""Role and permission domain models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Role(SQLModel, table=True):
    """Workspace scoped role definition."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_roles_workspace_key"),)

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True, nullable=False)
    key: str = Field(max_length=64, nullable=False)
    name: str = Field(max_length=128, nullable=False)
    description: str | None = Field(default=None, max_length=512)
    is_system: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class RolePermission(SQLModel, table=True):
    """Association between roles and permitted operations."""

    __tablename__ = "role_permissions"

    role_id: int = Field(foreign_key="roles.id", primary_key=True, nullable=False)
    operation: str = Field(max_length=64, primary_key=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class WorkspaceMemberRole(SQLModel, table=True):
    """Mapping table between workspace members and assigned roles."""

    __tablename__ = "workspace_member_roles"

    workspace_id: int = Field(foreign_key="workspaces.id", primary_key=True, nullable=False)
    user_id: int = Field(foreign_key="users.id", primary_key=True, nullable=False)
    role_id: int = Field(foreign_key="roles.id", primary_key=True, nullable=False)
    assigned_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

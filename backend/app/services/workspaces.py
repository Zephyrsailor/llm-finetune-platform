"""Workspace domain service."""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    Project,
    ProjectStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceStatus,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import ProjectRepository, WorkspaceRepository
from app.services.errors import (
    AccessDeniedError,
    ProjectConflictError,
    WorkspaceConflictError,
    WorkspaceNotFoundError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation, ensure_default_roles

DEFAULT_PROJECT_DIRECTORIES: tuple[tuple[str, str | None, str | None], ...] = (
    ("docs", "README.md", "# 项目说明\n\n该目录用于存放项目级文档、会议记录与操作指南。\n"),
    ("datasets", None, None),
    ("pipelines", None, None),
)


@dataclass(slots=True)
class WorkspaceSnapshot:
    """Lightweight workspace representation with members and projects."""

    workspace: Workspace
    members: list[tuple[WorkspaceMember, User]]
    projects: list[Project]


class WorkspaceService:
    """Provide high level workspace and project orchestration."""

    def __init__(self, session: Session):
        self._session = session
        self._workspaces = WorkspaceRepository(session)
        self._projects = ProjectRepository(session)
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)

    @contextmanager
    def _transaction(self):
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield

    # --------------------------------------------------------------------- #
    # Workspace operations
    # --------------------------------------------------------------------- #

    def create_workspace(
        self,
        *,
        current_user: User,
        name: str,
        description: str | None,
        plan: str | None,
        member_ids: Iterable[int],
        ip_address: str | None,
        user_agent: str | None,
    ) -> WorkspaceSnapshot:
        """Create a workspace with membership seeded from member_ids."""
        if self._workspaces.get_by_name(name) is not None:
            raise WorkspaceConflictError("工作空间名称已存在")

        unique_member_ids: OrderedDict[int, str] = OrderedDict()
        unique_member_ids[current_user.id] = "owner"
        for user_id in member_ids:
            if user_id == current_user.id:
                continue
            if self._users.get_by_id(user_id) is None:
                raise WorkspaceConflictError(f"成员 {user_id} 不存在")
            unique_member_ids[user_id] = "member"

        with self._transaction():
            workspace = Workspace(
                name=name,
                description=description,
                plan=plan,
                created_by=current_user.id,
            )
            workspace = self._workspaces.create(workspace)
            self._workspaces.upsert_members(
                workspace_id=workspace.id,
                members=[(uid, role) for uid, role in unique_member_ids.items()],
            )
            default_roles = ensure_default_roles(self._roles, workspace.id)
            admin_role_id = default_roles.get("workspace-admin")
            if admin_role_id is not None:
                self._roles.set_member_roles(
                    workspace_id=workspace.id,
                    user_id=current_user.id,
                    role_ids=[admin_role_id],
                )

        self._audits.record(
            event_type="workspace.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": workspace.id, "name": workspace.name},
        )

        members = list(self._workspaces.list_members(workspace.id))
        projects: list[Project] = []
        return WorkspaceSnapshot(workspace=workspace, members=members, projects=projects)

    def list_workspaces(self, *, current_user: User) -> list[WorkspaceSnapshot]:
        workspaces = self._workspaces.list_for_user(current_user.id)
        snapshots: list[WorkspaceSnapshot] = []
        for workspace in workspaces:
            members = list(self._workspaces.list_members(workspace.id))
            projects = list(self._projects.list_for_workspace(workspace.id))
            snapshots.append(WorkspaceSnapshot(workspace=workspace, members=members, projects=projects))
        return snapshots

    def get_workspace(self, *, workspace_id: int, current_user: User) -> WorkspaceSnapshot:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        if not self._workspaces.is_member(workspace_id, current_user.id):
            raise AccessDeniedError("没有访问该工作空间的权限")
        members = list(self._workspaces.list_members(workspace.id))
        projects = list(self._projects.list_for_workspace(workspace.id))
        return WorkspaceSnapshot(workspace=workspace, members=members, projects=projects)

    def update_workspace(
        self,
        *,
        workspace_id: int,
        current_user: User,
        name: str | None = None,
        description: str | None = None,
        plan: str | None = None,
        status: WorkspaceStatus | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> WorkspaceSnapshot:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if name and name != workspace.name:
            existing = self._workspaces.get_by_name(name)
            if existing and existing.id != workspace.id:
                raise WorkspaceConflictError("工作空间名称已存在")
            workspace.name = name

        if description is not None:
            workspace.description = description
        if plan is not None:
            workspace.plan = plan
        if status is not None:
            workspace.status = status

        with self._transaction():
            workspace = self._workspaces.update(workspace)

        self._audits.record(
            event_type="workspace.updated",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": workspace.id, "status": workspace.status},
        )

        members = list(self._workspaces.list_members(workspace.id))
        projects = list(self._projects.list_for_workspace(workspace.id))
        return WorkspaceSnapshot(workspace=workspace, members=members, projects=projects)

    # --------------------------------------------------------------------- #
    # Project operations
    # --------------------------------------------------------------------- #

    def create_project(
        self,
        *,
        workspace_id: int,
        current_user: User,
        name: str,
        description: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[WorkspaceSnapshot, list[str]]:
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

        existing = self._projects.get_by_name(workspace_id, name)
        if existing is not None:
            raise ProjectConflictError("项目名称在该工作空间内已存在")

        with self._transaction():
            project = Project(workspace_id=workspace_id, name=name, description=description)
            project = self._projects.create(project)

        created_paths = self._ensure_default_structure(workspace_id=workspace_id, project_id=project.id)

        self._audits.record(
            event_type="workspace.project.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": workspace_id, "project_id": project.id, "name": project.name},
        )

        members = list(self._workspaces.list_members(workspace_id))
        projects = list(self._projects.list_for_workspace(workspace_id))
        snapshot = WorkspaceSnapshot(workspace=workspace, members=members, projects=projects)
        return snapshot, created_paths

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #

    def _ensure_default_structure(self, *, workspace_id: int, project_id: int) -> list[str]:
        """Create default directory tree for a project and return created paths."""
        root = Path(settings.workspace_storage_root).expanduser()
        project_root = root / "workspaces" / str(workspace_id) / "projects" / str(project_id)
        project_root.mkdir(parents=True, exist_ok=True)

        created: list[str] = []
        for directory, placeholder_name, placeholder_content in DEFAULT_PROJECT_DIRECTORIES:
            target_dir = project_root / directory
            target_dir.mkdir(parents=True, exist_ok=True)
            created.append(str(target_dir.relative_to(root)))
            if placeholder_name and placeholder_content is not None:
                placeholder_path = target_dir / placeholder_name
                if not placeholder_path.exists():
                    placeholder_path.write_text(placeholder_content, encoding="utf-8")
                created.append(str(placeholder_path.relative_to(root)))
        return created

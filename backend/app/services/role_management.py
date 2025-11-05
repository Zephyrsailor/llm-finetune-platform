"""Role management service providing CRUD and assignment helpers."""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterable
from uuid import uuid4

from sqlmodel import Session

from app.models import User
from app.repositories.audit import AuditLogRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import (
    AccessDeniedError,
    RoleConflictError,
    RoleNotFoundError,
    WorkspaceNotFoundError,
)
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation, list_role_operation_options


class RoleManagementService:
    """Coordinate workspace role CRUD and assignments with permission checks."""

    def __init__(self, session: Session):
        self._session = session
        self._roles = RoleRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._users = UserRepository(session)
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

    def _ensure_workspace_member(self, workspace_id: int, user_id: int) -> None:
        if not self._workspaces.is_member(workspace_id, user_id):
            raise AccessDeniedError("没有访问该工作空间的权限")

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_matrix(self, *, workspace_id: int, current_user: User):
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在")

        self._ensure_workspace_member(workspace_id, current_user.id)

        roles = self._roles.list_roles(workspace_id)
        role_operations = {
            role.id: sorted(self._roles.list_role_operations(role.id))
            for role in roles
        }

        assignments = self._roles.list_assignments(workspace_id)
        assignment_map: dict[int, set[int]] = {}
        for row in assignments:
            assignment_map.setdefault(row.user_id, set()).add(row.role_id)

        member_rows = self._workspaces.list_members(workspace_id)
        member_assignments = [
            {
                "user_id": user.id,
                "email": user.email,
                "role_ids": sorted(assignment_map.get(user.id, set())),
            }
            for _, user in member_rows
        ]

        return {
            "roles": [
                {
                    "id": role.id,
                    "key": role.key,
                    "name": role.name,
                    "description": role.description,
                    "is_system": role.is_system,
                    "operations": role_operations.get(role.id, []),
                }
                for role in roles
            ],
            "assignments": member_assignments,
            "operations": list_role_operation_options(),
        }

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def create_role(
        self,
        *,
        workspace_id: int,
        current_user: User,
        name: str,
        description: str | None,
        operations: Iterable[str],
        ip_address: str | None,
        user_agent: str | None,
    ):
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

        validated_operations = self._validate_operations(operations)

        key = self._generate_role_key(workspace_id, name)

        with self._transaction():
            role = self._roles.upsert_role(
                workspace_id=workspace_id,
                key=key,
                name=name,
                description=description,
                is_system=False,
            )
            self._roles.set_role_operations(role_id=role.id, operations=validated_operations)

        self._audits.record(
            event_type="workspace.role.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "role_id": role.id,
                "name": role.name,
                "operations": validated_operations,
            },
        )

        return {
            "id": role.id,
            "key": role.key,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "operations": validated_operations,
        }

    def update_role(
        self,
        *,
        workspace_id: int,
        role_id: int,
        current_user: User,
        name: str | None,
        description: str | None,
        operations: Iterable[str] | None,
        ip_address: str | None,
        user_agent: str | None,
    ):
        role = self._roles.get(role_id)
        if role is None or role.workspace_id != workspace_id:
            raise RoleNotFoundError("角色不存在")

        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=current_user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if role.is_system and operations is not None:
            raise RoleConflictError("系统角色的权限不可修改")

        if role.is_system and name is not None and name != role.name:
            raise RoleConflictError("系统角色名称不可修改")

        validated_operations = self._validate_operations(operations) if operations is not None else None

        with self._transaction():
            updated_role = self._roles.upsert_role(
                workspace_id=workspace_id,
                key=role.key,
                name=name or role.name,
                description=description if description is not None else role.description,
                is_system=role.is_system,
            )
            if validated_operations is not None:
                self._roles.set_role_operations(role_id=updated_role.id, operations=validated_operations)
            else:
                validated_operations = self._roles.list_role_operations(updated_role.id)

        self._audits.record(
            event_type="workspace.role.updated",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "role_id": role_id,
                "name": name or role.name,
                "operations": validated_operations,
            },
        )

        return {
            "id": role_id,
            "key": role.key,
            "name": name or role.name,
            "description": description if description is not None else role.description,
            "is_system": role.is_system,
            "operations": validated_operations,
        }

    def set_member_roles(
        self,
        *,
        workspace_id: int,
        target_user_id: int,
        role_ids: Iterable[int],
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ):
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

        self._ensure_workspace_member(workspace_id, target_user_id)

        normalized_role_ids = sorted(set(role_ids))

        valid_role_ids = {role.id for role in self._roles.list_roles(workspace_id)}
        invalid_roles = set(normalized_role_ids) - valid_role_ids
        if invalid_roles:
            raise RoleNotFoundError(f"角色不存在: {sorted(invalid_roles)}")

        previous_assignments = self._roles.list_member_roles(workspace_id=workspace_id, user_id=target_user_id)
        previous_role_ids = {assignment.role_id for assignment in previous_assignments}

        with self._transaction():
            self._roles.set_member_roles(
                workspace_id=workspace_id,
                user_id=target_user_id,
                role_ids=normalized_role_ids,
            )

        updated_assignments = self._roles.list_member_roles(workspace_id=workspace_id, user_id=target_user_id)
        updated_role_ids = sorted(assignment.role_id for assignment in updated_assignments)

        self._audits.record(
            event_type="workspace.role.assignment",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "target_user_id": target_user_id,
                "previous_role_ids": sorted(previous_role_ids),
                "new_role_ids": updated_role_ids,
            },
        )

        target_user = self._users.get_by_id(target_user_id)
        return {
            "user_id": target_user_id,
            "email": target_user.email if target_user else "",
            "role_ids": updated_role_ids,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _validate_operations(self, operations: Iterable[str]) -> list[str]:
        ops = [operation for operation in operations if operation]
        if not ops:
            raise RoleConflictError("至少需要选择一个权限操作")

        allowed = {operation.value for operation in RoleOperation}
        unknown = sorted(set(ops) - allowed)
        if unknown:
            raise RoleConflictError(f"存在未定义的权限操作: {', '.join(unknown)}")
        return sorted(set(ops))

    def _generate_role_key(self, workspace_id: int, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower())
        if not base:
            base = "role"
        base = base.strip("-") or "role"
        candidate = base[:40]
        unique_suffix = uuid4().hex[:8]
        key = f"{candidate}-{unique_suffix}"
        if self._roles.get_by_key(workspace_id=workspace_id, key=key):
            key = f"{candidate}-{uuid4().hex[:8]}"
            if self._roles.get_by_key(workspace_id=workspace_id, key=key):
                key = f"role-{uuid4().hex[:8]}"
        return key

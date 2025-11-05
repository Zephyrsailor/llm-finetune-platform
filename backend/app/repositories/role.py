"""Role repository utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlmodel import Session

from app.models import Role, RolePermission, WorkspaceMemberRole


class RoleRepository:
    """Encapsulate CRUD operations for workspace roles and assignments."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, role_id: int) -> Role | None:
        """Fetch a role by primary key."""
        return self._session.get(Role, role_id)

    # ------------------------------------------------------------------ #
    # Role definitions
    # ------------------------------------------------------------------ #

    def get_by_key(self, workspace_id: int, key: str) -> Role | None:
        statement = select(Role).where(Role.workspace_id == workspace_id, Role.key == key)
        return self._session.exec(statement).scalars().first()

    def list_roles(self, workspace_id: int) -> Sequence[Role]:
        statement = (
            select(Role)
            .where(Role.workspace_id == workspace_id)
            .order_by(Role.is_system.desc(), Role.created_at.asc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def upsert_role(
        self,
        *,
        workspace_id: int,
        key: str,
        name: str,
        description: str | None,
        is_system: bool,
    ) -> Role:
        role = self.get_by_key(workspace_id, key)
        now = datetime.utcnow()
        if role is None:
            role = Role(
                workspace_id=workspace_id,
                key=key,
                name=name,
                description=description,
                is_system=is_system,
                created_at=now,
                updated_at=now,
            )
        else:
            role.name = name
            role.description = description
            role.is_system = is_system
            role.updated_at = now
        self._session.add(role)
        self._session.flush()
        self._session.refresh(role)
        return role

    def set_role_operations(self, *, role_id: int, operations: Iterable[str]) -> None:
        target_operations = {operation for operation in operations}
        existing_operations = set(
            self._session.exec(select(RolePermission.operation).where(RolePermission.role_id == role_id)).scalars().all()
        )

        to_add = target_operations - existing_operations
        to_remove = existing_operations - target_operations

        for operation in to_add:
            self._session.add(RolePermission(role_id=role_id, operation=operation))

        if to_remove:
            delete_statement = (
                delete(RolePermission)
                .where(RolePermission.role_id == role_id)
                .where(RolePermission.operation.in_(to_remove))
            )
            self._session.exec(delete_statement)

        self._session.flush()

    def list_role_operations(self, role_id: int) -> list[str]:
        """Return operations bound to the given role."""
        statement = select(RolePermission.operation).where(RolePermission.role_id == role_id)
        return list(self._session.exec(statement).scalars().all())

    # ------------------------------------------------------------------ #
    # Member assignments
    # ------------------------------------------------------------------ #

    def list_member_roles(self, *, workspace_id: int, user_id: int) -> Sequence[WorkspaceMemberRole]:
        statement = (
            select(WorkspaceMemberRole)
            .where(
                WorkspaceMemberRole.workspace_id == workspace_id,
                WorkspaceMemberRole.user_id == user_id,
            )
            .order_by(WorkspaceMemberRole.assigned_at.asc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def list_operations_for_member(self, *, workspace_id: int, user_id: int) -> set[str]:
        """Return the set of operations granted to the member via assigned roles."""
        statement = (
            select(RolePermission.operation)
            .join(WorkspaceMemberRole, RolePermission.role_id == WorkspaceMemberRole.role_id)
            .where(WorkspaceMemberRole.workspace_id == workspace_id)
            .where(WorkspaceMemberRole.user_id == user_id)
        )
        return set(self._session.exec(statement).scalars().all())

    def list_assignments(self, workspace_id: int) -> list[WorkspaceMemberRole]:
        """Return all role assignments for the workspace."""
        statement = select(WorkspaceMemberRole).where(WorkspaceMemberRole.workspace_id == workspace_id)
        return list(self._session.exec(statement).scalars().all())

    def set_member_roles(
        self,
        *,
        workspace_id: int,
        user_id: int,
        role_ids: Iterable[int],
    ) -> None:
        desired = set(role_ids)
        existing_rows = self.list_member_roles(workspace_id=workspace_id, user_id=user_id)
        existing = {row.role_id for row in existing_rows}

        to_add = desired - existing
        to_remove = existing - desired

        now = datetime.utcnow()
        for role_id in to_add:
            self._session.add(
                WorkspaceMemberRole(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role_id=role_id,
                    assigned_at=now,
                )
            )

        if to_remove:
            delete_statement = (
                delete(WorkspaceMemberRole)
                .where(WorkspaceMemberRole.workspace_id == workspace_id)
                .where(WorkspaceMemberRole.user_id == user_id)
                .where(WorkspaceMemberRole.role_id.in_(to_remove))
            )
            self._session.exec(delete_statement)

        self._session.flush()

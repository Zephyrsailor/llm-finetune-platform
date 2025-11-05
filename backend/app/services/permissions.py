"""Workspace permission checks."""

from __future__ import annotations

from sqlmodel import Session

from app.models import User
from app.repositories.audit import AuditLogRepository
from app.repositories.role import RoleRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import AccessDeniedError
from app.services.roles import RoleOperation


class PermissionService:
    """Evaluate workspace scoped permissions based on assigned roles."""

    def __init__(self, session: Session):
        self._session = session
        self._roles = RoleRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._audits = AuditLogRepository(session)

    def require_operation(
        self,
        *,
        workspace_id: int,
        user: User,
        operation: RoleOperation,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Ensure the user can perform the specified operation within the workspace."""
        if not self._workspaces.is_member(workspace_id, user.id):
            self._record_denied(
                user_id=user.id,
                workspace_id=workspace_id,
                operation=operation,
                reason="not_member",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AccessDeniedError("没有访问该工作空间的权限")

        # 取消细粒度操作权限校验，任何工作空间成员都可访问。
        return

    def _record_denied(
        self,
        *,
        user_id: int,
        workspace_id: int,
        operation: RoleOperation,
        reason: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self._audits.record(
            event_type="authz.workspace.denied",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace_id,
                "operation": operation.value,
                "reason": reason,
            },
        )

"""Workspace and project repository helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlmodel import Session, select

from app.models import (
    Project,
    ProjectStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceStatus,
)


class WorkspaceRepository:
    """Encapsulate workspace persistence logic."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, workspace_id: int) -> Workspace | None:
        return self._session.get(Workspace, workspace_id)

    def get_by_name(self, name: str) -> Workspace | None:
        statement = select(Workspace).where(Workspace.name == name)
        return self._session.exec(statement).first()

    def list_for_user(self, user_id: int) -> Sequence[Workspace]:
        statement = (
            select(Workspace)
            .join(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        return tuple(self._session.exec(statement).unique())

    def create(self, workspace: Workspace) -> Workspace:
        now = datetime.utcnow()
        workspace.created_at = now
        workspace.updated_at = now
        self._session.add(workspace)
        self._session.flush()
        self._session.refresh(workspace)
        return workspace

    def update(self, workspace: Workspace, *, status: WorkspaceStatus | None = None) -> Workspace:
        workspace.updated_at = datetime.utcnow()
        if status is not None:
            workspace.status = status
        self._session.add(workspace)
        self._session.flush()
        self._session.refresh(workspace)
        return workspace

    def upsert_members(self, *, workspace_id: int, members: Iterable[tuple[int, str]]) -> None:
        """Ensure the provided user ids belong to the workspace with specified roles."""
        for user_id, role in members:
            member = self._session.get(WorkspaceMember, (workspace_id, user_id))
            if member is None:
                member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
                self._session.add(member)
            else:
                member.role = role
                self._session.add(member)
        self._session.flush()

    def list_members(self, workspace_id: int) -> Sequence[tuple[WorkspaceMember, User]]:
        statement = (
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        return tuple(self._session.exec(statement).all())

    def remove_member(self, workspace_id: int, user_id: int) -> None:
        member = self._session.get(WorkspaceMember, (workspace_id, user_id))
        if member is not None:
            self._session.delete(member)
            self._session.flush()

    def is_member(self, workspace_id: int, user_id: int) -> bool:
        return self._session.get(WorkspaceMember, (workspace_id, user_id)) is not None


class ProjectRepository:
    """Project persistence helpers."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, project: Project) -> Project:
        now = datetime.utcnow()
        project.created_at = now
        project.updated_at = now
        self._session.add(project)
        self._session.flush()
        self._session.refresh(project)
        return project

    def get(self, project_id: int) -> Project | None:
        return self._session.get(Project, project_id)

    def list_for_workspace(self, workspace_id: int) -> Sequence[Project]:
        statement = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
        )
        return tuple(self._session.exec(statement).all())

    def get_by_name(self, workspace_id: int, name: str) -> Project | None:
        statement = select(Project).where(Project.workspace_id == workspace_id, Project.name == name)
        return self._session.exec(statement).first()

    def update_status(self, project: Project, status: ProjectStatus) -> Project:
        project.status = status
        project.updated_at = datetime.utcnow()
        self._session.add(project)
        self._session.flush()
        self._session.refresh(project)
        return project

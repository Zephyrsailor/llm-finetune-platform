"""Workspace API integration tests."""

from __future__ import annotations

from datetime import timedelta
import secrets
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core import security
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models import (
    AuditLog,
    Project,
    Role,
    RolePermission,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
)
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.services.roles import DEFAULT_ROLE_MATRIX, RoleOperation


@pytest.fixture()
def client(tmp_path) -> Iterator[tuple[TestClient, Session]]:
    """Provide API client backed by in-memory SQLite and isolated storage root."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override_session():
        with Session(engine) as session:
            yield session

    original_storage_root = settings.workspace_storage_root
    settings.workspace_storage_root = str(tmp_path / "storage")
    app.dependency_overrides[get_session] = _override_session

    test_client = TestClient(app)
    try:
        yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        settings.workspace_storage_root = original_storage_root
        SQLModel.metadata.drop_all(engine)


def _create_user(engine, email: str) -> User:
    with Session(engine) as session:
        repo = UserRepository(session)
        user = repo.create(email=email, password_hash=security.hash_password("Password123"))
        return user


def _auth_header(user: User) -> dict[str, str]:
    token = security.create_token(
        {"sub": str(user.id), "scope": "access", "jti": secrets.token_hex(8)},
        timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_workspace_and_project_generates_structure(client, tmp_path):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")

    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Demo Workspace", "description": "Init workspace", "plan": "standard"},
        headers=_auth_header(owner),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    workspace_id = data["id"]
    assert data["status"] == WorkspaceStatus.ACTIVE
    assert any(member["user_id"] == owner.id for member in data["members"])

    project_resp = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "Demo Project"},
        headers=_auth_header(owner),
    )
    assert project_resp.status_code == 201, project_resp.text
    payload = project_resp.json()
    created_paths = payload["created_paths"]

    storage_root = Path(settings.workspace_storage_root)
    for rel_path in created_paths:
        absolute = storage_root / rel_path
        assert absolute.exists(), f"{absolute} should exist"

    with Session(engine) as session:
        ws = session.get(Workspace, workspace_id)
        assert ws is not None
        projects = session.exec(select(Project).where(Project.workspace_id == workspace_id)).all()
        assert len(projects) == 1
        members = session.exec(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        ).all()
        assert len(members) == 1

        roles = session.exec(select(Role).where(Role.workspace_id == workspace_id)).all()
        assert len(roles) == len(DEFAULT_ROLE_MATRIX)
        role_keys = {role.key for role in roles}
        expected_keys = {definition.key for definition in DEFAULT_ROLE_MATRIX}
        assert role_keys == expected_keys

        admin_definition = next(defn for defn in DEFAULT_ROLE_MATRIX if defn.key == "workspace-admin")
        admin_role = next(role for role in roles if role.key == "workspace-admin")
        admin_operations = set(
            session.exec(select(RolePermission.operation).where(RolePermission.role_id == admin_role.id))
        )
        expected_operations = {operation.value for operation in admin_definition.operations}
        assert admin_operations == expected_operations

        assignments = session.exec(
            select(WorkspaceMemberRole).where(
                WorkspaceMemberRole.workspace_id == workspace_id,
                WorkspaceMemberRole.user_id == owner.id,
            )
        ).all()
        assert any(assignment.role_id == admin_role.id for assignment in assignments)


def test_non_member_cannot_view_workspace(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    outsider = _create_user(engine, "outsider@example.com")

    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Secure Workspace"},
        headers=_auth_header(owner),
    )
    workspace_id = response.json()["id"]

    forbidden = test_client.get(f"/api/v1/workspaces/{workspace_id}", headers=_auth_header(outsider))
    assert forbidden.status_code == 403


def test_workspace_update_allows_members_without_roles(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    member = _create_user(engine, "member@example.com")

    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Secure Workspace", "member_ids": [member.id]},
        headers=_auth_header(owner),
    )
    workspace_id = response.json()["id"]

    allowed = test_client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"plan": "premium"},
        headers=_auth_header(member),
    )
    assert allowed.status_code == 200
    assert allowed.json()["plan"] == "premium"

    with Session(engine) as session:
        audit_entries = session.exec(select(AuditLog).where(AuditLog.event_type == "authz.workspace.denied")).all()
        assert not any(
            entry.payload.get("workspace_id") == workspace_id and entry.payload.get("operation") == RoleOperation.APPROVAL_MANAGE.value
            for entry in audit_entries
        ), "成员更新工作空间时不应再记录权限拒绝"


def test_archive_workspace(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Archive Workspace"},
        headers=_auth_header(owner),
    )
    workspace_id = response.json()["id"]

    update_resp = test_client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"status": WorkspaceStatus.ARCHIVED},
        headers=_auth_header(owner),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == WorkspaceStatus.ARCHIVED

    with Session(engine) as session:
        ws = session.get(Workspace, workspace_id)
        assert ws is not None
        assert ws.status == WorkspaceStatus.ARCHIVED


def test_role_matrix_management_flow(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    member = _create_user(engine, "member@example.com")

    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": "Role Workspace", "member_ids": [member.id]},
        headers=_auth_header(owner),
    )
    workspace_id = response.json()["id"]

    # Owner can view role matrix
    matrix_resp = test_client.get(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers=_auth_header(owner),
    )
    assert matrix_resp.status_code == 200
    matrix_payload = matrix_resp.json()
    assert len(matrix_payload["roles"]) == len(DEFAULT_ROLE_MATRIX)
    assert any(role["key"] == "workspace-admin" for role in matrix_payload["roles"])
    assert "operations" in matrix_payload
    assert any(assignment["user_id"] == owner.id for assignment in matrix_payload["assignments"])

    # 普通成员也可创建自定义角色
    member_create = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        json={"name": "自定义角色", "description": "测试", "operations": ["evaluation_view"]},
        headers=_auth_header(member),
    )
    assert member_create.status_code == 201, member_create.text
    custom_role = member_create.json()
    assert custom_role["is_system"] is False
    custom_role_id = custom_role["id"]

    # Update the custom role operations
    update_resp = test_client.patch(
        f"/api/v1/workspaces/{workspace_id}/roles/{custom_role_id}",
        json={
            "operations": ["evaluation_view"],
            "description": "仅需要查看评估",
        },
        headers=_auth_header(owner),
    )
    assert update_resp.status_code == 200, update_resp.text
    updated_role = update_resp.json()
    assert updated_role["operations"] == ["evaluation_view"]
    assert updated_role["description"] == "仅需要查看评估"

    # Assign the role to member
    assign_resp = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/members/{member.id}/roles",
        json={"role_ids": [custom_role_id]},
        headers=_auth_header(owner),
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assignment_payload = assign_resp.json()
    assert assignment_payload["role_ids"] == [custom_role_id]

    with Session(engine) as session:
        assignments = session.exec(
            select(WorkspaceMemberRole).where(
                WorkspaceMemberRole.workspace_id == workspace_id,
                WorkspaceMemberRole.user_id == member.id,
            )
        ).all()
        assert {assignment.role_id for assignment in assignments} == {custom_role_id}

        audit_entries = session.exec(
            select(AuditLog).where(AuditLog.event_type == "workspace.role.assignment")
        ).all()
        assert audit_entries, "Expected audit log entries for role assignment"

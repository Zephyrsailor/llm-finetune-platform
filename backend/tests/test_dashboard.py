"""Dashboard API integration tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core import database as db
from app.core import security
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models import (
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetVersion,
    DatasetVersionStatus,
    Project,
    ProjectStatus,
    Role,
    User,
    Workspace,
    WorkspaceMember,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.tasks import data_cleaning


@pytest.fixture()
def dashboard_client(tmp_path) -> Iterator[tuple[TestClient, Session]]:
    """Provide API client backed by in-memory SQLite."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    original_engine = db.engine
    original_db_url = settings.database_url
    original_task_engine = data_cleaning.engine
    db.engine = engine
    settings.database_url = "sqlite://"
    data_cleaning.engine = engine

    def _override_session():
        with Session(engine) as session:
            yield session

    original_storage_root = settings.workspace_storage_root
    original_max_size = settings.max_dataset_size_bytes
    original_eager = settings.celery_task_always_eager
    settings.workspace_storage_root = str(tmp_path / "storage")
    settings.max_dataset_size_bytes = 2 * 1024 * 1024
    settings.celery_task_always_eager = True
    app.dependency_overrides[get_session] = _override_session

    test_client = TestClient(app)
    try:
        yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        settings.workspace_storage_root = original_storage_root
        settings.max_dataset_size_bytes = original_max_size
        settings.celery_task_always_eager = original_eager
        SQLModel.metadata.drop_all(engine)
        db.engine = original_engine
        settings.database_url = original_db_url
        data_cleaning.engine = original_task_engine


def _create_user(engine, email: str) -> User:
    with Session(engine) as session:
        repo = UserRepository(session)
        return repo.create(email=email, password_hash=security.hash_password("Password123"))


def _auth_header(user: User) -> dict[str, str]:
    token = security.create_token(
        {"sub": str(user.id), "scope": "access"},
        timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {token}"}


def _create_workspace_via_api(
    test_client: TestClient,
    engine,
    owner: User,
    *,
    name: str,
    description: str = "demo workspace",
    member_ids: list[int] | None = None,
) -> Workspace:
    payload = {
        "name": name,
        "description": description,
        "member_ids": member_ids or [],
    }
    response = test_client.post(
        "/api/v1/workspaces",
        json=payload,
        headers=_auth_header(owner),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    workspace_id = data["id"]
    with Session(engine) as session:
        workspace = session.get(Workspace, workspace_id)
        assert workspace is not None
        member = session.get(WorkspaceMember, (workspace_id, owner.id))
        assert member is not None
        return workspace


def _assign_role(engine, workspace_id: int, user_id: int, role_key: str) -> None:
    with Session(engine) as session:
        repo = RoleRepository(session)
        role: Role | None = repo.get_by_key(workspace_id, role_key)
        assert role is not None
        repo.set_member_roles(workspace_id=workspace_id, user_id=user_id, role_ids=[role.id])
        session.commit()


def test_dashboard_summary_empty_workspace(dashboard_client):
    test_client, engine = dashboard_client
    owner = _create_user(engine, "owner@example.com")
    _create_workspace_via_api(test_client, engine, owner, name="workspace-empty")

    response = test_client.get("/api/v1/dashboard/summary", headers=_auth_header(owner))
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["workspaces"]) == 1
    stages = {stage["stage"]: stage for stage in payload["workspaces"][0]["stages"]}
    assert stages["data_ingestion"]["status"] == "not_started"
    assert stages["training"]["status"] == "not_started"
    assert stages["evaluation"]["status"] == "not_started"
    assert stages["deployment"]["status"] == "not_started"


def test_dashboard_summary_with_data_and_events(dashboard_client):
    test_client, engine = dashboard_client
    owner = _create_user(engine, "metrics@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="workspace-data")

    with Session(engine) as session:
        dataset = Dataset(
            workspace_id=workspace.id,
            name="training-dataset",
            description="",
            source_type="upload",
            created_by=owner.id,
        )
        session.add(dataset)
        session.commit()
        session.refresh(dataset)

        version = DatasetVersion(
            dataset_id=dataset.id,
            version=1,
            status=DatasetVersionStatus.COMPLETED,
            created_by=owner.id,
        )
        session.add(version)
        session.commit()
        session.refresh(version)

        job = DataCleaningJob(
            dataset_version_id=version.id,
            status=DataCleaningJobStatus.COMPLETED,
            logs_path="workspaces/1/datasets/1/v1/logs/job-1.log",
        )
        session.add(job)

        project = Project(
            workspace_id=workspace.id,
            name="llm-training",
            status=ProjectStatus.ACTIVE,
            description="",
        )
        session.add(project)

        session.commit()

        audits = AuditLogRepository(session)
        audits.record(
            event_type="evaluation.pipeline.completed",
            user_id=owner.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace.id,
                "responsible": owner.email,
                "notes": "评估分数 0.82",
            },
        )
        audits.record(
            event_type="deployment.workflow.failed",
            user_id=owner.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace.id,
                "notes": "部署节点离线",
            },
        )

    response = test_client.get("/api/v1/dashboard/summary", headers=_auth_header(owner))
    assert response.status_code == 200
    payload = response.json()
    summary = payload["workspaces"][0]
    stages = {stage["stage"]: stage for stage in summary["stages"]}
    assert stages["data_ingestion"]["status"] == "completed"
    assert "v1" in stages["data_ingestion"]["notes"]
    assert stages["training"]["status"] == "in_progress"
    assert stages["evaluation"]["status"] == "completed"
    assert stages["deployment"]["status"] == "unknown"


def test_dashboard_permissions_and_filters(dashboard_client):
    test_client, engine = dashboard_client
    owner = _create_user(engine, "owner2@example.com")
    viewer = _create_user(engine, "viewer@example.com")

    denied_workspace = _create_workspace_via_api(
        test_client,
        engine,
        owner,
        name="workspace-denied",
        member_ids=[viewer.id],
    )
    allowed_workspace = _create_workspace_via_api(
        test_client,
        engine,
        owner,
        name="workspace-allowed",
        member_ids=[viewer.id],
    )

    response = test_client.get("/api/v1/dashboard/summary", headers=_auth_header(viewer))
    assert response.status_code == 200
    payload = response.json()
    workspace_ids = sorted(item["workspace_id"] for item in payload["workspaces"])
    assert workspace_ids == sorted([denied_workspace.id, allowed_workspace.id])

    response = test_client.get(
        f"/api/v1/dashboard/summary?workspace_id={denied_workspace.id}",
        headers=_auth_header(viewer),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["workspace_id"] == denied_workspace.id

    response = test_client.get(
        f"/api/v1/dashboard/summary?workspace_id={allowed_workspace.id}",
        headers=_auth_header(viewer),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["workspace_id"] == allowed_workspace.id

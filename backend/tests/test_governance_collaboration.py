"""Governance collaboration API tests for comments and approvals."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from app.models import (
    ApprovalStatus,
    ApprovalTaskStatus,
    AuditLog,
    Dataset,
    DatasetSourceType,
    DatasetVersion,
    DatasetVersionStatus,
    TrainingJob,
    TrainingJobStatus,
    WorkspaceMember,
)
from app.repositories.role import RoleRepository

pytest_plugins = ["backend.tests.test_datasets"]


def _bootstrap_comment_entities(engine, workspace_id: int, owner_id: int) -> Tuple[int, int]:
    """Create dataset version and training job for collaboration tests."""
    with Session(engine) as session:
        dataset = Dataset(
            workspace_id=workspace_id,
            name="governance-dataset",
            description="dataset for collaboration tests",
            source_type=DatasetSourceType.UPLOAD,
            storage_path="/tmp/governance-dataset",
            data_type="jsonl",
            mime_type="application/json",
            file_size_bytes=1024,
            created_by=owner_id,
        )
        session.add(dataset)
        session.flush()
        version = DatasetVersion(
            dataset_id=dataset.id,
            version=1,
            status=DatasetVersionStatus.COMPLETED,
            created_by=owner_id,
        )
        session.add(version)
        session.flush()
        training_job = TrainingJob(
            workspace_id=workspace_id,
            project_id=None,
            dataset_version_id=version.id,
            base_model="llama-3-8b",
            status=TrainingJobStatus.RUNNING,
            params_json={"learning_rate": 2e-4},
            notes="governance training job",
            scheduled_by=owner_id,
            requested_gpus=1,
            queue_name="default",
        )
        session.add(training_job)
        session.commit()
        return version.id, training_job.id


def test_comments_and_approvals_flow(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "governance-owner@example.com")
    reviewer = _create_user(engine, "governance-reviewer@example.com")
    approver = _create_user(engine, "governance-approver@example.com")

    workspace = _create_workspace_via_api(test_client, engine, owner, name="Gov Workspace")
    dataset_version_id, training_job_id = _bootstrap_comment_entities(engine, workspace.id, owner.id)

    with Session(engine) as session:
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=reviewer.id, role="member"))
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=approver.id, role="member"))
        role_repo = RoleRepository(session)
        reviewer_role = role_repo.get_by_key(workspace.id, "business-reviewer")
        admin_role = role_repo.get_by_key(workspace.id, "workspace-admin")
        if reviewer_role is None or admin_role is None:
            session.commit()
            raise AssertionError("默认角色未初始化")
        role_repo.set_member_roles(
            workspace_id=workspace.id,
            user_id=reviewer.id,
            role_ids=[reviewer_role.id],
        )
        role_repo.set_member_roles(
            workspace_id=workspace.id,
            user_id=approver.id,
            role_ids=[reviewer_role.id, admin_role.id],
        )
        session.commit()

    # Create comment with mention and attachment
    comment_resp = test_client.post(
        "/api/v1/governance/comments",
        json={
            "workspace_id": workspace.id,
            "entity_type": "dataset_version",
            "entity_id": dataset_version_id,
            "body": "请确认样本质量。",
            "mentions": [reviewer.id],
            "attachments": [
                {"name": "quality-report.pdf", "url": "https://example.com/quality-report.pdf"}
            ],
            "context": "dataset-review",
        },
        headers=_auth_header(owner),
    )
    assert comment_resp.status_code == 201, comment_resp.text
    comment_payload = comment_resp.json()
    assert comment_payload["mentions"][0]["id"] == reviewer.id
    assert comment_payload["attachments"][0]["name"] == "quality-report.pdf"

    # Reviewer lists comments
    list_resp = test_client.get(
        "/api/v1/governance/comments",
        params={
            "workspace_id": workspace.id,
            "entity_type": "dataset_version",
            "entity_id": dataset_version_id,
        },
        headers=_auth_header(reviewer),
    )
    assert list_resp.status_code == 200, list_resp.text
    comments = list_resp.json()
    assert any(item["id"] == comment_payload["id"] for item in comments)

    with Session(engine) as session:
        audit_event = session.exec(
            select(AuditLog).where(AuditLog.event_type == "governance.comment.created")
        ).first()
        assert audit_event is not None

    # Create approval request
    approval_resp = test_client.post(
        "/api/v1/governance/approvals",
        json={
            "workspace_id": workspace.id,
            "entity_type": "training_job",
            "entity_id": training_job_id,
            "title": "训练结果审批",
            "description": "请确认指标达标。",
            "approver_ids": [reviewer.id, approver.id],
            "due_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        },
        headers=_auth_header(owner),
    )
    assert approval_resp.status_code == 201, approval_resp.text
    approval_payload = approval_resp.json()
    assert approval_payload["status"] == ApprovalStatus.PENDING.value
    assert len(approval_payload["tasks"]) == 2

    request_id = approval_payload["id"]

    # Reviewer approves
    approve_resp = test_client.post(
        f"/api/v1/governance/approvals/{request_id}/decisions",
        json={"status": ApprovalTaskStatus.APPROVED.value},
        headers=_auth_header(reviewer),
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approve_payload = approve_resp.json()
    assert approve_payload["status"] == ApprovalStatus.PENDING.value

    # Another approver rejects with notes
    reject_resp = test_client.post(
        f"/api/v1/governance/approvals/{request_id}/decisions",
        json={"status": ApprovalTaskStatus.REJECTED.value, "notes": "需补充评估报告"},
        headers=_auth_header(approver),
    )
    assert reject_resp.status_code == 200, reject_resp.text
    reject_payload = reject_resp.json()
    assert reject_payload["status"] == ApprovalStatus.REJECTED.value

    with Session(engine) as session:
        decision_logs = session.exec(
            select(AuditLog).where(AuditLog.event_type == "governance.approval.decision")
        ).all()
        assert decision_logs, "审批决策应写入审计日志"

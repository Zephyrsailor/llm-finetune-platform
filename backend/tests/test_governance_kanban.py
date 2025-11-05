"""Governance kanban API tests."""

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
    AuditLog,
    Dataset,
    DatasetSourceType,
    DatasetVersion,
    DatasetVersionStatus,
    KanbanCard,
    KanbanStage,
    KanbanStatus,
    TrainingJob,
    TrainingJobStatus,
    User,
)


pytest_plugins = ["backend.tests.test_datasets"]


def _bootstrap_kanban_entities(
    engine,
    workspace_id: int,
    owner: User,
) -> None:
    with Session(engine) as session:
        dataset = Dataset(
            workspace_id=workspace_id,
            name="support-faq",
            description="Dataset for Q&A",
            source_type=DatasetSourceType.UPLOAD,
            source_uri=None,
            storage_path="/tmp/support",
            data_type="jsonl",
            mime_type="application/json",
            file_size_bytes=1024,
            checksum_sha256="abc",
            tags=["faq"],
            created_by=owner.id,
        )
        session.add(dataset)
        session.flush()
        version = DatasetVersion(
            dataset_id=dataset.id,
            version=1,
            status=DatasetVersionStatus.PROCESSING,
            created_by=owner.id,
        )
        session.add(version)
        session.flush()
        training_job = TrainingJob(
            workspace_id=workspace_id,
            project_id=None,
            dataset_version_id=version.id,
            base_model="llama-3-8b",
            status=TrainingJobStatus.RUNNING,
            params_json={"lr": 2e-4},
            notes="initial fine-tune",
            scheduled_by=owner.id,
            requested_gpus=1,
            queue_name="default",
        )
        session.add(training_job)
        session.commit()


def _find_card(response_json: dict, stage: KanbanStage) -> dict:
    for column in response_json["columns"]:
        for task in column["tasks"]:
            if task["stage"] == stage.value:
                return task
    raise AssertionError(f"No card found for stage {stage}")


def test_governance_kanban_board_flow(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "pm@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Governance Lab")
    _bootstrap_kanban_entities(engine, workspace.id, owner)

    # Fetch board and ensure dataset/training cards exist
    board_resp = test_client.get(
        "/api/v1/governance/kanban/board",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert board_resp.status_code == 200, board_resp.text
    board_payload = board_resp.json()
    dataset_card = _find_card(board_payload, KanbanStage.DATA)
    training_card = _find_card(board_payload, KanbanStage.TRAINING)
    assert dataset_card["status"] == KanbanStatus.IN_PROGRESS.value
    assert training_card["status"] == KanbanStatus.IN_PROGRESS.value
    assert dataset_card["linked_entity"]["status"] == DatasetVersionStatus.PROCESSING.value

    # Update dataset card assignment and due date
    due_at = datetime.utcnow().replace(microsecond=0) + timedelta(days=2)
    patch_resp = test_client.patch(
        f"/api/v1/governance/kanban/cards/{dataset_card['id']}",
        json={
            "assignee_id": owner.id,
            "due_at": due_at.isoformat(),
            "reminder_minutes_before": 60,
        },
        headers=_auth_header(owner),
    )
    assert patch_resp.status_code == 200, patch_resp.text
    updated_card = patch_resp.json()
    assert updated_card["assignee"]["id"] == owner.id
    assert updated_card["reminder_minutes_before"] == 60

    with Session(engine) as session:
        logs = session.exec(
            select(AuditLog).where(AuditLog.event_type == "governance.kanban.card_updated")
        ).all()
        assert logs, "Audit log for card update should exist"
        notification = session.exec(
            select(AuditLog).where(AuditLog.event_type == "governance.notification.queued")
        ).first()
        assert notification is not None

    # Create manual follow-up task
    create_resp = test_client.post(
        "/api/v1/governance/kanban/cards",
        json={
            "workspace_id": workspace.id,
            "stage": KanbanStage.DEPLOYMENT.value,
            "status": KanbanStatus.BACKLOG.value,
            "title": "发布检查清单",
            "description": "列出上线前需确认项",
        },
        headers=_auth_header(owner),
    )
    assert create_resp.status_code == 201, create_resp.text
    created_card = create_resp.json()
    assert created_card["stage"] == KanbanStage.DEPLOYMENT.value
    assert created_card["linked_entity"] is None

    # Move manual card to done column
    manual_reorder = test_client.post(
        "/api/v1/governance/kanban/cards/reorder",
        json={
            "workspace_id": workspace.id,
            "moves": [
                {
                    "card_id": created_card["id"],
                    "status": KanbanStatus.DONE.value,
                    "order_index": 2.0,
                    "stage": KanbanStage.DEPLOYMENT.value,
                }
            ],
        },
        headers=_auth_header(owner),
    )
    assert manual_reorder.status_code == 200, manual_reorder.text
    manual_board = manual_reorder.json()
    deployment_card = _find_card(manual_board, KanbanStage.DEPLOYMENT)
    assert deployment_card["status"] == KanbanStatus.DONE.value

    with Session(engine) as session:
        cards = session.exec(
            select(KanbanCard).where(KanbanCard.workspace_id == workspace.id)
        ).all()
        assert len(cards) >= 3

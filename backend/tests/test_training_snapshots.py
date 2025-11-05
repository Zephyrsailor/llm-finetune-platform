"""Training snapshot API integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from app.core.config import settings
from app.models import TrainingRun, TrainingSnapshot
from app.services.training_snapshots import TrainingSnapshotService

pytest_plugins = ["backend.tests.test_datasets"]


def _prepare_training_job(
    test_client: TestClient,
    engine: Session,
    *,
    owner,
    workspace_id: int,
) -> tuple[int, int]:
    """Create dataset, format and training job, returning job_id and dataset_version_id."""
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace_id),
            "name": "snapshot-dataset",
            "source_type": "upload",
        },
        files={
            "upload_file": ("data.jsonl", b'{"text": "hello snapshot"}\n', "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "snapshot preparation"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    version_payload = version_resp.json()
    dataset_version_id = version_payload["version"]["id"]

    format_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{dataset_version_id}/formats/run",
        headers=_auth_header(owner),
    )
    assert format_resp.status_code == 202, format_resp.text
    format_records = format_resp.json()
    dataset_format_version_id = format_records[0]["id"]

    list_templates = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace_id},
        headers=_auth_header(owner),
    )
    assert list_templates.status_code == 200, list_templates.text
    template_id = list_templates.json()[0]["id"]

    job_resp = test_client.post(
        "/api/v1/training/jobs",
        json={
            "workspace_id": workspace_id,
            "dataset_version_id": dataset_version_id,
            "dataset_format_version_id": dataset_format_version_id,
            "training_template_id": template_id,
            "params": {"num_epochs": 1},
            "requested_gpus": 1,
            "queue_name": "default",
        },
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 202, job_resp.text
    job_payload = job_resp.json()
    return job_payload["id"], dataset_version_id


def test_snapshot_resume_and_rollback_flow(client: tuple[TestClient, Session]):
    test_client, engine = client
    owner = _create_user(engine, "snapshot-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Snapshot Lab")

    job_id, _ = _prepare_training_job(
        test_client,
        engine,
        owner=owner,
        workspace_id=workspace.id,
    )

    list_resp = test_client.get(
        "/api/v1/training/snapshots",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200, list_resp.text
    snapshots = list_resp.json()
    assert snapshots, "初始训练应生成至少一个快照"
    snapshot_id = snapshots[0]["id"]

    with Session(engine) as db:
        service = TrainingSnapshotService(db)
        snapshot_obj = service.get_snapshot(snapshot_id, owner)
        assert snapshot_obj.id == snapshot_id

    detail_resp = test_client.get(
        f"/api/v1/training/snapshots/{snapshot_id}",
        headers=_auth_header(owner),
    )
    assert detail_resp.status_code == 200, detail_resp.text

    resume_resp = test_client.post(
        f"/api/v1/training/snapshots/{snapshot_id}:resume",
        json={"notes": "自动恢复测试"},
        headers=_auth_header(owner),
    )
    assert resume_resp.status_code == 202, resume_resp.text
    resumed_run = resume_resp.json()
    assert resumed_run["status"] == "completed"
    assert resumed_run["resumed_from_snapshot_id"] == snapshot_id
    with Session(engine) as check_session:
        persisted_run = check_session.get(TrainingRun, resumed_run["id"])
        assert persisted_run is not None
        assert persisted_run.resumed_from_snapshot_id == snapshot_id

    workspace_list_after_resume = test_client.get(
        "/api/v1/training/snapshots",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert workspace_list_after_resume.status_code == 200
    assert len(workspace_list_after_resume.json()) >= 2

    rollback_resp = test_client.post(
        f"/api/v1/training/snapshots/{snapshot_id}:rollback",
        json={"reason": "验证回滚"},
        headers=_auth_header(owner),
    )
    assert rollback_resp.status_code == 200, rollback_resp.text
    rollback_payload = rollback_resp.json()
    assert rollback_payload["restored_at"] is not None
    assert rollback_payload["restored_by"] == owner.id
    with Session(engine) as check_session:
        persisted_snapshot = check_session.get(TrainingSnapshot, snapshot_id)
        assert persisted_snapshot is not None
        assert persisted_snapshot.restored_at is not None
        assert persisted_snapshot.restored_by == owner.id

    active_path = (
        Path(settings.workspace_storage_root)
        / "workspaces"
        / str(workspace.id)
        / "training"
        / str(job_id)
        / "active"
    )
    assert (active_path / "evaluation.json").exists()
    assert (active_path / "model.safetensors").exists()

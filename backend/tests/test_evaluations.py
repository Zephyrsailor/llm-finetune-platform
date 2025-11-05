"""Evaluation API integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from app.core.config import settings
from app.models import (
    DatasetFormatStatus,
    DatasetFormatType,
    DatasetVersion,
    User,
    Workspace,
)
from app.repositories.format import DatasetFormatVersionRepository
from app.repositories.training import TrainingAlertRepository

pytest_plugins = ["backend.tests.test_datasets"]


def _create_dataset_and_version(
    test_client: TestClient,
    engine: Session,
    owner: User,
    workspace: Workspace,
) -> int:
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "evaluation-corpus",
            "source_type": "upload",
            "data_type": "jsonl",
            "tags": json.dumps(["evaluation"]),
        },
        files={
            "upload_file": (
                "eval.jsonl",
                b'{"prompt": "hello", "answer": "world"}\n{"prompt": "foo", "answer": "bar"}\n',
                "application/json",
            )
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "evaluation baseline"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    version_id = version_resp.json()["version"]["id"]

    with Session(engine) as session:
        version = session.get(DatasetVersion, version_id)
        assert version is not None
        version.quality_summary_path = f"datasets/{version_id}/quality.json"
        session.add(version)
        session.flush()

        format_repo = DatasetFormatVersionRepository(session)
        format_record = format_repo.create(
            dataset_version_id=version_id,
            format=DatasetFormatType.JSONL,
        )
        format_repo.update_status(
            format_record,
            status=DatasetFormatStatus.COMPLETED,
            path=f"datasets/{version_id}/formats/jsonl",
            mark_started=True,
            mark_finished=True,
        )
        format_repo.set_active(format_record.id)
        session.commit()

    return version_id


def _create_training_run(
    test_client: TestClient,
    owner: User,
    workspace: Workspace,
    dataset_version_id: int,
    evaluation_dataset_version_id: int | None = None,
) -> int:
    template_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert template_resp.status_code == 200, template_resp.text
    template_id = template_resp.json()[0]["id"]

    params = {"num_epochs": 1}
    if evaluation_dataset_version_id is not None:
        params["evaluation"] = {"dataset_version_id": evaluation_dataset_version_id}

    job_resp = test_client.post(
        "/api/v1/training/jobs",
        json={
            "workspace_id": workspace.id,
            "dataset_version_id": dataset_version_id,
            "training_template_id": template_id,
            "params": params,
            "requested_gpus": 1,
            "queue_name": "default",
        },
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 202, job_resp.text
    created = job_resp.json()
    latest_run = created["latest_run"]
    assert latest_run is not None
    return latest_run["id"]


def test_evaluation_job_lifecycle(client):
    test_client, engine = client
    owner = _create_user(engine, "qa-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Evaluation Lab")

    dataset_version_id = _create_dataset_and_version(test_client, engine, owner, workspace)

    templates_resp = test_client.get(
        "/api/v1/evaluations/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200, templates_resp.text
    templates = templates_resp.json()
    assert len(templates) >= 1
    template_id = templates[0]["id"]

    job_resp = test_client.post(
        "/api/v1/evaluations/jobs",
        data={
            "workspace_id": str(workspace.id),
            "evaluation_template_id": str(template_id),
            "dataset_version_id": str(dataset_version_id),
        },
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 201, job_resp.text
    job_payload = job_resp.json()
    assert job_payload["status"] == "pending"
    assert job_payload["trigger_mode"] == "manual"

    jobs_resp = test_client.get(
        "/api/v1/evaluations/jobs",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert jobs, "应返回至少一个评估任务"
    evaluation_job = jobs[0]
    assert evaluation_job["status"] == "completed"
    assert evaluation_job["metrics"]["example_count"] >= 2
    assert evaluation_job["training_run_id"] is None
    assert "thresholds" in evaluation_job["metrics"]

    detail_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{evaluation_job['id']}",
        headers=_auth_header(owner),
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["report_path"] is not None

    storage_root = Path(settings.workspace_storage_root)
    report_file = storage_root / detail["report_path"]
    assert report_file.exists()

    export_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{evaluation_job['id']}/export",
        headers=_auth_header(owner),
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/markdown")

    export_json = test_client.get(
        f"/api/v1/evaluations/jobs/{evaluation_job['id']}/export",
        params={"format": "json"},
        headers=_auth_header(owner),
    )
    assert export_json.status_code == 200
    assert export_json.headers["content-type"].startswith("application/json")

    report_resp = test_client.get(
        f"/api/v1/evaluations/reports/{evaluation_job['id']}",
        headers=_auth_header(owner),
    )
    assert report_resp.status_code == 200
    report_payload = report_resp.json()
    assert report_payload["job"]["id"] == evaluation_job["id"]
    assert report_payload["job"]["trigger_mode"] == "manual"
    assert "metrics" in report_payload
    assert "cases" in report_payload

    pdf_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{evaluation_job['id']}/export",
        params={"format": "pdf"},
        headers=_auth_header(owner),
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")

    share_resp = test_client.post(
        f"/api/v1/evaluations/reports/{evaluation_job['id']}/share",
        headers=_auth_header(owner),
    )
    assert share_resp.status_code == 200
    share_payload = share_resp.json()
    shared_report = test_client.get(share_payload["share_path"])
    assert shared_report.status_code == 200


def test_create_evaluation_job_with_uploaded_dataset(client):
    test_client, engine = client
    owner = _create_user(engine, "qa-upload@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Upload Lab")

    templates_resp = test_client.get(
        "/api/v1/evaluations/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200
    template_id = templates_resp.json()[0]["id"]

    file_content = b'{"text": "hello", "label": "greeting"}\n'
    job_resp = test_client.post(
        "/api/v1/evaluations/jobs",
        data={
            "workspace_id": str(workspace.id),
            "evaluation_template_id": str(template_id),
        },
        files={"dataset_file": ("custom.jsonl", file_content, "application/json")},
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 201, job_resp.text
    job = job_resp.json()
    assert job["id"] is not None

    detail_resp = test_client.get(
        f"/api/v1/evaluations/jobs/{job['id']}",
        headers=_auth_header(owner),
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "completed"
    assert detail["metrics"]["example_count"] >= 1
    assert detail["trigger_mode"] == "manual"


def test_training_completion_triggers_automatic_evaluation(client):
    test_client, engine = client
    owner = _create_user(engine, "qa-auto@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Automation Lab")

    dataset_version_id = _create_dataset_and_version(test_client, engine, owner, workspace)
    run_id = _create_training_run(
        test_client,
        owner,
        workspace,
        dataset_version_id,
        evaluation_dataset_version_id=dataset_version_id,
    )

    jobs_resp = test_client.get(
        "/api/v1/evaluations/jobs",
        params={"workspace_id": workspace.id, "training_run_id": run_id},
        headers=_auth_header(owner),
    )
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert jobs, "自动化评估任务应已创建"
    auto_job = jobs[0]
    assert auto_job["trigger_mode"] == "automatic"
    assert auto_job["metrics"]["example_count"] >= 1

    runs_resp = test_client.get(
        "/api/v1/training/monitor/runs",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert runs_resp.status_code == 200
    run_payload = next(item for item in runs_resp.json() if item["run_id"] == run_id)
    assert run_payload["latest_evaluation"]["job_id"] == auto_job["id"]


def test_evaluation_threshold_creates_training_alert(client):
    test_client, engine = client
    owner = _create_user(engine, "qa-alert@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Alert Lab")

    dataset_version_id = _create_dataset_and_version(test_client, engine, owner, workspace)
    run_id = _create_training_run(
        test_client,
        owner,
        workspace,
        dataset_version_id,
        evaluation_dataset_version_id=dataset_version_id,
    )

    templates_resp = test_client.get(
        "/api/v1/evaluations/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    template_id = templates_resp.json()[0]["id"]

    degraded_content = b'{"reference": "alpha", "prediction": "beta"}\n'
    manual_resp = test_client.post(
        "/api/v1/evaluations/jobs",
        data={
            "workspace_id": str(workspace.id),
            "evaluation_template_id": str(template_id),
            "training_run_id": str(run_id),
        },
        files={"dataset_file": ("degraded.jsonl", degraded_content, "application/json")},
        headers=_auth_header(owner),
    )
    assert manual_resp.status_code == 201, manual_resp.text

    with Session(engine) as session:
        alert_repo = TrainingAlertRepository(session)
        alerts = alert_repo.list_for_run(run_id)
        assert any(
            alert.rule.name.startswith("[自动评估]") for alert in alerts
        ), "评估阈值触发后应产生训练告警"

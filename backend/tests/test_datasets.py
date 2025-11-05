"""Dataset API integration tests."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core import security
from app.core.config import settings
from app.core import database as db
from app.core.database import get_session
from app.tasks import data_cleaning, training as training_tasks, evaluation as evaluation_tasks, deployment as deployment_tasks
from app.main import app
from app.models import (
    DataCleaningJob,
    DataCleaningJobStatus,
    Dataset,
    DatasetFormatStatus,
    DatasetFormatType,
    DatasetFormatVersion,
    DatasetSourceType,
    DatasetVersion,
    DatasetVersionStatus,
    QualityEvaluationStatus,
    User,
    Workspace,
    WorkspaceMember,
)
from app.repositories.user import UserRepository


@pytest.fixture()
def client(tmp_path) -> Iterator[tuple[TestClient, Session]]:
    """Provide API client backed by in-memory SQLite."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    print("DEBUG-CREATED-ENGINE", id(engine))
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("DEBUG-TABLES", [row[0] for row in rows])

    original_engine = db.engine
    original_db_url = settings.database_url
    original_task_engine = data_cleaning.engine
    original_training_engine = training_tasks.engine
    original_evaluation_engine = evaluation_tasks.engine
    original_deployment_engine = deployment_tasks.engine
    db.engine = engine
    settings.database_url = "sqlite://"
    data_cleaning.engine = engine
    training_tasks.engine = engine
    evaluation_tasks.engine = engine
    deployment_tasks.engine = engine

    def _override_session():
        with Session(engine) as session:
            print("DEBUG-SESSION-ENGINE", id(engine))
            yield session

    original_storage_root = settings.workspace_storage_root
    original_max_size = settings.max_dataset_size_bytes
    original_eager = settings.celery_task_always_eager
    settings.workspace_storage_root = str(tmp_path / "storage")
    settings.max_dataset_size_bytes = 2 * 1024 * 1024  # 2 MiB
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
        training_tasks.engine = original_training_engine
        evaluation_tasks.engine = original_evaluation_engine
        deployment_tasks.engine = original_deployment_engine


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
    name: str = "Data Lab",
    description: str = "for datasets",
) -> Workspace:
    response = test_client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": description},
        headers=_auth_header(owner),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    workspace_id = data["id"]
    with Session(engine) as session:
        workspace = session.get(Workspace, workspace_id)
        assert workspace is not None
        # Ensure owner membership exists.
        member = session.get(WorkspaceMember, (workspace_id, owner.id))
        assert member is not None
        return workspace


def test_create_dataset_via_upload(client, tmp_path):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    file_content = b'{"prompt": "hello", "completion": "world"}\n'
    response = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "support-faq",
            "source_type": DatasetSourceType.UPLOAD.value,
            "data_type": "jsonl",
            "tags": json.dumps(["faq", "support"]),
        },
        files={
            "upload_file": ("faq.jsonl", file_content, "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["name"] == "support-faq"
    assert payload["source_type"] == DatasetSourceType.UPLOAD.value
    assert payload["file_size_bytes"] == len(file_content)
    assert payload["mime_type"] == "application/json"
    assert payload["tags"] == ["faq", "support"]

    storage_root = Path(settings.workspace_storage_root)
    assert payload["storage_path"] is not None
    stored_file = storage_root / payload["storage_path"]
    assert stored_file.exists()
    assert stored_file.read_bytes() == file_content


def test_create_dataset_version_triggers_cleaning_job(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "pipeline-dataset",
            "source_type": DatasetSourceType.UPLOAD.value,
        },
        files={
            "upload_file": ("data.jsonl", b"{}", "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "initial run"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    payload = version_resp.json()
    assert payload["version"]["status"] == DatasetVersionStatus.COMPLETED.value
    assert payload["job"]["status"] == DataCleaningJobStatus.COMPLETED.value
    assert payload["job"]["export_manifest"] is not None
    assert "jsonl" in payload["job"]["export_manifest"]
    assert payload["quality_job"] is not None
    assert payload["quality_job"]["status"] == QualityEvaluationStatus.COMPLETED.value

    summary_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/cleaning/summary",
        headers=_auth_header(owner),
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["stats"]["total_rows"] == 1
    assert summary["export_manifest"]["jsonl"].endswith(".jsonl")

    export_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/cleaning/export",
        params={"format": "csv"},
        headers=_auth_header(owner),
    )
    assert export_resp.status_code == 200
    assert export_resp.content

    storage_root = Path(settings.workspace_storage_root)
    log_path = storage_root / payload["job"]["logs_path"]
    assert log_path.exists()
    assert "initial run" in log_path.read_text(encoding="utf-8")

    quality_summary_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/quality/summary",
        headers=_auth_header(owner),
    )
    assert quality_summary_resp.status_code == 200
    quality_summary = quality_summary_resp.json()
    assert quality_summary["stats"]["total_rows"] == 1
    assert quality_summary["report_manifest"]["json"].endswith("summary.json")

    quality_export_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/quality/export",
        params={"format": "json"},
        headers=_auth_header(owner),
    )
    assert quality_export_resp.status_code == 200
    assert quality_export_resp.headers["content-type"].startswith("application/json")


def test_external_dataset_requires_source_uri(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    response = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "external-dataset",
            "source_type": DatasetSourceType.EXTERNAL.value,
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 400


def test_reference_dataset_reuses_metadata(client):
    test_client, engine = client
    owner = _create_user(engine, "owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    original = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "origin",
            "source_type": DatasetSourceType.UPLOAD.value,
            "tags": "alpha,beta",
        },
        files={
            "upload_file": ("origin.jsonl", b"line", "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert original.status_code == 201
    original_payload = original.json()

    reference = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "reference-copy",
            "source_type": DatasetSourceType.REFERENCE.value,
            "reference_dataset_id": str(original_payload["id"]),
        },
        headers=_auth_header(owner),
    )
    assert reference.status_code == 201, reference.text
    reference_payload = reference.json()
    assert reference_payload["storage_path"] == original_payload["storage_path"]
    assert reference_payload["checksum_sha256"] == original_payload["checksum_sha256"]
    assert reference_payload["file_size_bytes"] == original_payload["file_size_bytes"]


def test_dataset_format_conversion_flow(client):
    test_client, engine = client
    owner = _create_user(engine, "owner-format@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "format-dataset",
            "source_type": DatasetSourceType.UPLOAD.value,
        },
        files={
            "upload_file": ("data.jsonl", b'{"text": "hello world"}\n', "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "format pipeline"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    version_payload = version_resp.json()
    version_id = version_payload["version"]["id"]

    run_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats/run",
        headers=_auth_header(owner),
    )
    assert run_resp.status_code == 202, run_resp.text
    run_data = run_resp.json()
    assert len(run_data) == len(list(DatasetFormatType))
    assert {item["format"] for item in run_data} == {fmt.value for fmt in DatasetFormatType}
    for item in run_data:
        assert item["status"] == DatasetFormatStatus.COMPLETED.value
        assert item["path"] is not None
        assert item["logs_path"] is not None

    jsonl_record = next(item for item in run_data if item["format"] == DatasetFormatType.JSONL.value)
    storage_root = Path(settings.workspace_storage_root)
    output_file = storage_root / jsonl_record["path"]
    log_file = storage_root / jsonl_record["logs_path"]
    assert output_file.exists()
    assert log_file.exists()
    assert "格式转换完成" in log_file.read_text(encoding="utf-8")

    list_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats",
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert len(listed) == len(run_data)

    export_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats/export",
        params={"fmt": DatasetFormatType.JSONL.value},
        headers=_auth_header(owner),
    )
    assert export_resp.status_code == 200
    assert export_resp.content
    assert export_resp.headers["content-type"].startswith("application/json")

    rerun_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats/run",
        json={"formats": [DatasetFormatType.JSONL.value]},
        headers=_auth_header(owner),
    )
    assert rerun_resp.status_code == 202, rerun_resp.text
    rerun_data = rerun_resp.json()
    assert len(rerun_data) == 1
    new_jsonl_record = rerun_data[0]
    assert new_jsonl_record["format"] == DatasetFormatType.JSONL.value

    activate_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats/{jsonl_record['id']}/activate",
        headers=_auth_header(owner),
    )
    assert activate_resp.status_code == 200
    activated = activate_resp.json()
    assert activated["id"] == jsonl_record["id"]
    assert activated["is_active"] is True

    list_after = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{version_id}/formats",
        headers=_auth_header(owner),
    ).json()
    jsonl_entries = [item for item in list_after if item["format"] == DatasetFormatType.JSONL.value]
    assert len(jsonl_entries) == 2
    active_ids = [item["id"] for item in jsonl_entries if item["is_active"]]
    assert active_ids == [jsonl_record["id"]]
    inactive_ids = [item["id"] for item in jsonl_entries if not item["is_active"]]
    assert new_jsonl_record["id"] in inactive_ids

    with Session(engine) as session:
        version = session.get(DatasetVersion, version_id)
        assert version is not None
        assert version.stats_json is not None
        assert "formats" in version.stats_json
        assert DatasetFormatType.JSONL.value in version.stats_json["formats"]
        stored_record = session.get(DatasetFormatVersion, jsonl_record["id"])
        assert stored_record is not None
        assert stored_record.is_active is True
        assert stored_record.logs_path == jsonl_record["logs_path"]
        newer_record = session.get(DatasetFormatVersion, new_jsonl_record["id"])
        assert newer_record is not None
        assert newer_record.is_active is False


def test_list_datasets_and_versions(client):
    test_client, engine = client
    owner = _create_user(engine, "owner-list@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner)

    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "list-me",
            "source_type": DatasetSourceType.UPLOAD.value,
        },
        files={
            "upload_file": ("data.jsonl", b"{\n}", "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text

    list_resp = test_client.get(
        f"/api/v1/datasets?workspace_id={workspace.id}",
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200
    datasets = list_resp.json()
    assert any(item["id"] == dataset_id for item in datasets)

    versions_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions",
        headers=_auth_header(owner),
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["dataset_id"] == dataset_id


def test_cleaning_template_assignment_and_execution(client, tmp_path):
    test_client, engine = client
    owner = _create_user(engine, "owner-templ@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="workspace-cleaning")

    dataset_rows = [
        '{"id": 1, "text": "hello world", "email": "foo@example.com"}',
        '{"id": 1, "text": "hello world", "email": "foo@example.com"}',
        '{"id": 2, "text": "Noise foo", "email": "bar@example.com"}',
    ]
    dataset_content = "\n".join(dataset_rows)
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "cleanable",
            "source_type": DatasetSourceType.UPLOAD.value,
        },
        files={
            "upload_file": ("clean.jsonl", dataset_content.encode("utf-8"), "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    template_resp = test_client.post(
        "/api/v1/datasets/cleaning/templates",
        json={
            "workspace_id": workspace.id,
            "name": "默认清洗",
            "steps": [
                {"type": "deduplicate", "field": "id"},
                {"type": "drop_noise", "field": "text", "keywords": ["noise"]},
                {"type": "mask_field", "field": "email", "replacement": "[masked]"},
            ],
        },
        headers=_auth_header(owner),
    )
    assert template_resp.status_code == 201, template_resp.text
    template_id = template_resp.json()["id"]

    assign_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/cleaning/assignment",
        json={"template_id": template_id, "enabled": True},
        headers=_auth_header(owner),
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["template_id"] == template_id

    assignment_get = test_client.get(
        f"/api/v1/datasets/{dataset_id}/cleaning/assignment",
        headers=_auth_header(owner),
    )
    assert assignment_get.status_code == 200
    assert assignment_get.json()["template_id"] == template_id

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "with template"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    payload = version_resp.json()
    assert payload["job"]["template_id"] == template_id

    summary_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/cleaning/summary",
        headers=_auth_header(owner),
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["stats"]["duplicates_removed"] == 1
    assert summary["stats"]["noise_removed"] == 1
    assert summary["stats"]["masked_fields"] >= 1

    export_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/cleaning/export",
        params={"format": "jsonl"},
        headers=_auth_header(owner),
    )
    assert export_resp.status_code == 200
    assert export_resp.content

    quality_resp = test_client.get(
        f"/api/v1/datasets/{dataset_id}/versions/{payload['version']['id']}/quality/summary",
        headers=_auth_header(owner),
    )
    assert quality_resp.status_code == 200
    quality_info = quality_resp.json()
    assert quality_info["stats"]["total_rows"] == 1
    assert quality_info["stats"]["duplicate_rows"] >= 0

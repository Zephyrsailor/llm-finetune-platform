"""Training wizard draft and validation tests."""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)

pytest_plugins = ["backend.tests.test_datasets"]


def _prepare_dataset_resources(test_client: TestClient, engine, owner, workspace_id: int) -> tuple[int, int]:
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace_id),
            "name": "wizard-dataset",
            "source_type": "upload",
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
        json={"notes": "wizard validation"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    dataset_version_id = version_resp.json()["version"]["id"]

    format_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{dataset_version_id}/formats/run",
        headers=_auth_header(owner),
    )
    assert format_resp.status_code == 202, format_resp.text
    format_records = format_resp.json()
    assert format_records, "format conversion should return records"
    dataset_format_version_id = format_records[0]["id"]

    return dataset_version_id, dataset_format_version_id


def test_training_wizard_draft_and_validation(client: tuple[TestClient, Session]):
    test_client, engine = client
    owner = _create_user(engine, "wizard@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Wizard Lab")

    # Retrieve built-in templates
    templates_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200, templates_resp.text
    template_id = templates_resp.json()[0]["id"]

    # Draft initially empty
    draft_resp = test_client.get(
        "/api/v1/training/wizard/draft",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert draft_resp.status_code == 200, draft_resp.text
    assert draft_resp.json()["payload"] is None

    # Save draft payload
    save_resp = test_client.post(
        "/api/v1/training/wizard/draft",
        json={
            "workspace_id": workspace.id,
            "payload": {"step": 1, "templateId": template_id, "requestedGpus": 1, "queueName": "default"}
        },
        headers=_auth_header(owner),
    )
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json()["payload"]["templateId"] == template_id

    draft_resp = test_client.get(
        "/api/v1/training/wizard/draft",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert draft_resp.status_code == 200
    assert draft_resp.json()["payload"]["templateId"] == template_id
    assert draft_resp.json()["payload"]["requestedGpus"] == 1
    assert draft_resp.json()["payload"]["queueName"] == "default"

    dataset_version_id, dataset_format_version_id = _prepare_dataset_resources(
        test_client, engine, owner, workspace.id
    )

    # Validate configuration
    validate_resp = test_client.post(
        "/api/v1/training/wizard/validate",
        json={
            "workspace_id": workspace.id,
            "dataset_version_id": dataset_version_id,
            "dataset_format_version_id": dataset_format_version_id,
            "training_template_id": template_id,
            "requested_gpus": 1,
            "queue_name": "default",
            "params": {"num_epochs": 1},
        },
        headers=_auth_header(owner),
    )
    assert validate_resp.status_code == 200, validate_resp.text
    config = validate_resp.json()
    assert config["dataset_version_id"] == dataset_version_id
    assert config["training_template_id"] == template_id
    assert config["params"]["num_epochs"] == 1
    assert config["requested_gpus"] == 1
    assert config["queue_name"] == "default"

    # Invalid dataset version
    invalid_resp = test_client.post(
        "/api/v1/training/wizard/validate",
        json={
            "workspace_id": workspace.id,
            "dataset_version_id": 999999,
        },
        headers=_auth_header(owner),
    )
    assert invalid_resp.status_code == 400

    # Clear draft by sending empty payload
    clear_resp = test_client.post(
        "/api/v1/training/wizard/draft",
        json={"workspace_id": workspace.id, "payload": {}},
        headers=_auth_header(owner),
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["payload"] is None

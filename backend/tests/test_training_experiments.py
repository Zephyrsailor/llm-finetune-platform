"""Training experiment metadata, comparison, and export tests."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from app.core.config import settings

pytest_plugins = ["backend.tests.test_datasets"]


def _prepare_training_run(
    test_client: TestClient,
    *,
    owner,
    workspace_id: int,
    dataset_name: str,
    template_index: int = 0,
) -> Tuple[int, int]:
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace_id),
            "name": dataset_name,
            "source_type": "upload",
        },
        files={
            "upload_file": ("data.jsonl", b'{"text": "metadata-run"}\n', "application/json"),
        },
        headers=_auth_header(owner),
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": f"metadata {dataset_name}"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    dataset_version = version_resp.json()["version"]
    dataset_version_id = dataset_version["id"]

    # Trigger format standardisation to satisfy training prerequisites.
    format_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{dataset_version_id}/formats/run",
        headers=_auth_header(owner),
    )
    assert format_resp.status_code == 202, format_resp.text
    format_records = format_resp.json()
    assert format_records, "格式转换应返回记录"
    dataset_format_version_id = format_records[0]["id"]

    templates_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace_id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200, templates_resp.text
    templates = templates_resp.json()
    assert templates, "应存在至少一个训练模板"
    template_id = templates[template_index]["id"]

    job_resp = test_client.post(
        "/api/v1/training/jobs",
        json={
            "workspace_id": workspace_id,
            "dataset_version_id": dataset_version_id,
            "dataset_format_version_id": dataset_format_version_id,
            "training_template_id": template_id,
            "params": {"num_epochs": 1, "learning_rate": 5e-4},
            "requested_gpus": 1,
            "queue_name": "default",
            "notes": f"job for {dataset_name}",
        },
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 202, job_resp.text
    payload = job_resp.json()
    latest_run = payload["latest_run"]
    assert latest_run is not None, "创建任务后应立即生成运行记录"
    return payload["id"], latest_run["id"]


def test_training_experiment_metadata_and_detail(client: tuple[TestClient, Session], tmp_path):
    original_root = settings.workspace_storage_root
    settings.workspace_storage_root = str(tmp_path / "storage")
    try:
        test_client, engine = client
        owner = _create_user(engine, "experiment-owner@example.com")
        workspace = _create_workspace_via_api(test_client, engine, owner, name="Experiment Lab")

        job_id, run_id = _prepare_training_run(
            test_client,
            owner=owner,
            workspace_id=workspace.id,
            dataset_name="experiment-dataset-a",
        )

        list_resp = test_client.get(
            "/api/v1/training/experiments",
            params={"workspace_id": workspace.id},
            headers=_auth_header(owner),
        )
        assert list_resp.status_code == 200, list_resp.text
        payload = list_resp.json()
        assert payload, "应返回至少一条训练运行摘要"
        summary = payload[0]
        assert summary["job_id"] == job_id
        assert summary["metrics"], "摘要应包含最终指标"
        assert summary["resource"]["requested_gpus"] == 1

        detail_resp = test_client.get(
            f"/api/v1/training/experiments/{run_id}",
            headers=_auth_header(owner),
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        assert detail["metadata"]["dataset"]["dataset_name"] == "experiment-dataset-a"
        assert "snapshots" in detail["metadata"]
        assert detail["metadata"]["metrics"]["final"]
        assert detail["metadata"]["resource"]["cost_estimate_usd"] is not None
    finally:
        settings.workspace_storage_root = original_root


def test_training_experiment_compare_and_export(client: tuple[TestClient, Session], tmp_path):
    original_root = settings.workspace_storage_root
    settings.workspace_storage_root = str(tmp_path / "storage")
    try:
        test_client, engine = client
        owner = _create_user(engine, "experiment-compare@example.com")
        workspace = _create_workspace_via_api(test_client, engine, owner, name="Compare Lab")

        _, run_a = _prepare_training_run(
            test_client,
            owner=owner,
            workspace_id=workspace.id,
            dataset_name="experiment-dataset-a",
        )
        _, run_b = _prepare_training_run(
            test_client,
            owner=owner,
            workspace_id=workspace.id,
            dataset_name="experiment-dataset-b",
        )

        compare_resp = test_client.post(
            "/api/v1/training/experiments/compare",
            json={"run_a_id": run_a, "run_b_id": run_b},
            headers=_auth_header(owner),
        )
        assert compare_resp.status_code == 200, compare_resp.text
        comparison = compare_resp.json()
        assert (
            comparison["diff"]["parameters"]
            or comparison["diff"]["final_metrics"]
            or comparison["diff"]["dataset"]
        )

        export_resp = test_client.post(
            "/api/v1/training/experiments/export",
            json={
                "workspace_id": workspace.id,
                "run_ids": [run_a, run_b],
                "format": "json",
            },
            headers=_auth_header(owner),
        )
        assert export_resp.status_code == 200, export_resp.text
        export_payload = export_resp.json()
        export_path = Path(export_payload["path"])
        assert export_path.exists()
        exported_content = export_path.read_text(encoding="utf-8")
        assert f"\"run_id\": {run_a}" in exported_content
        assert f"\"run_id\": {run_b}" in exported_content
    finally:
        settings.workspace_storage_root = original_root

"""Training API integration tests."""

from __future__ import annotations

import json
import math
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import DatasetVersion, DatasetFormatVersion, DatasetFormatType, DatasetFormatStatus

pytest.importorskip("torch", reason="需要安装 torch 以运行真实训练流程")
pytest.importorskip("transformers", reason="需要安装 transformers 以运行真实训练流程")
pytest.importorskip("peft", reason="需要安装 peft 以运行真实训练流程")

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from app.core.config import settings
from app.core.celery_app import celery_app

pytest_plugins = ["backend.tests.test_datasets"]


def test_training_template_and_job_flow(client: tuple[TestClient, Session], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "celery_task_always_eager", True)
    celery_app.conf.task_always_eager = True
    test_client, engine = client
    owner = _create_user(engine, "trainer@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Training Lab")

    # Built-in templates should be provisioned automatically.
    list_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200, list_resp.text
    templates = list_resp.json()
    assert len(templates) >= 3
    builtin_names = {template["name"] for template in templates}
    assert "LoRA 默认模板" in builtin_names

    # Create a custom template.
    create_resp = test_client.post(
        "/api/v1/training/templates",
        json={
            "workspace_id": workspace.id,
            "name": "客服场景 LoRA",
            "description": "针对客服对话的快速调参模板",
            "base_model": "meta-llama/Llama-3-8b-instruct",
            "adapter_type": "lora",
            "params": {
                "learning_rate": 3e-4,
                "lora_rank": 12,
                "num_epochs": 2,
                "per_device_train_batch_size": 4,
            },
        },
        headers=_auth_header(owner),
    )
    assert create_resp.status_code == 201, create_resp.text
    template_payload = create_resp.json()
    template_id = template_payload["id"]
    assert template_payload["params"]["learning_rate"] == 3e-4

    # Update template parameters.
    update_resp = test_client.patch(
        f"/api/v1/training/templates/{template_id}",
        json={"params": {"learning_rate": 2e-4, "lora_rank": 16}},
        headers=_auth_header(owner),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["params"]["lora_rank"] == 16

    # Clone template.
    clone_resp = test_client.post(
        f"/api/v1/training/templates/{template_id}:clone",
        json={"name": "客服场景副本"},
        headers=_auth_header(owner),
    )
    assert clone_resp.status_code == 201, clone_resp.text
    clone_payload = clone_resp.json()
    clone_id = clone_payload["id"]
    assert clone_payload["name"] == "客服场景副本"

    # Prepare dataset and version to back training job.
    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "training-support-dataset",
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
        json={"notes": "用于训练模板测试"},
        headers=_auth_header(owner),
    )
    assert version_resp.status_code == 201, version_resp.text
    version_payload = version_resp.json()
    dataset_version_id = version_payload["version"]["id"]

    with Session(engine) as session:
        version_obj = session.get(DatasetVersion, dataset_version_id)
        assert version_obj is not None
        version_obj.quality_summary_path = "workspaces/quality/summary.json"
        session.add(version_obj)
        session.flush()
        format_record = DatasetFormatVersion(
            dataset_version_id=version_obj.id,
            format=DatasetFormatType.JSONL,
            status=DatasetFormatStatus.COMPLETED,
            path="storage/formats/data.jsonl",
            is_active=True,
        )
        session.add(format_record)
        session.commit()
        dataset_format_version_id = format_record.id

    # 创建训练任务并验证 Celery 占位任务执行。
    job_payload = {
        "workspace_id": workspace.id,
        "dataset_version_id": dataset_version_id,
        "dataset_format_version_id": dataset_format_version_id,
        "training_template_id": template_id,
        "params": {"num_epochs": 2},
        "requested_gpus": 1,
        "queue_name": "default",
        "notes": "自动调参测试",
    }
    create_job_resp = test_client.post(
        "/api/v1/training/jobs",
        json=job_payload,
        headers=_auth_header(owner),
    )
    assert create_job_resp.status_code == 202, create_job_resp.text
    job_data = create_job_resp.json()
    assert job_data["status"] == "completed"
    assert job_data["latest_run"] is not None
    metrics = job_data["latest_run"]["metrics"]
    assert math.isfinite(metrics["final_loss"])
    assert metrics["final_loss"] > 0
    assert math.isfinite(metrics["final_perplexity"])
    assert metrics["final_perplexity"] >= 1
    assert job_data["requested_gpus"] == 1
    assert job_data["queue_name"] == "default"

    job_id = job_data["id"]
    get_job_resp = test_client.get(
        f"/api/v1/training/jobs/{job_id}",
        headers=_auth_header(owner),
    )
    assert get_job_resp.status_code == 200, get_job_resp.text
    fetched = get_job_resp.json()
    assert fetched["latest_run"]["exit_code"] == 0
    assert fetched["latest_run"]["artifact_uri"].endswith(f"/{job_id}/artifacts")
    assert fetched["requested_gpus"] == 1
    assert fetched["queue_name"] == "default"


def test_training_template_validation_errors(client: tuple[TestClient, Session]):
    test_client, engine = client
    owner = _create_user(engine, "validator@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Validation Lab")

    response = test_client.post(
        "/api/v1/training/templates",
        json={
            "workspace_id": workspace.id,
            "name": "Invalid Template",
            "base_model": "meta-llama/Llama-3-8b-instruct",
            "adapter_type": "lora",
            "params": {"learning_rate": 0.5},
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 422
    detail = response.json()
    assert "learning_rate" in detail["detail"]


def test_training_job_invalid_gpu_count(client: tuple[TestClient, Session], monkeypatch: pytest.MonkeyPatch):
    test_client, engine = client
    owner = _create_user(engine, "gpu-check@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="GPU Lab")

    list_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    template_id = list_resp.json()[0]["id"]

    dataset_resp = test_client.post(
        "/api/v1/datasets",
        data={
            "workspace_id": str(workspace.id),
            "name": "gpu-dataset",
            "source_type": "upload",
        },
        files={
            "upload_file": ("data.jsonl", b'{"text": "hello"}\n', "application/json"),
        },
        headers=_auth_header(owner),
    )
    dataset_id = dataset_resp.json()["id"]

    version_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        json={"notes": "gpu-validation"},
        headers=_auth_header(owner),
    )
    dataset_version_id = version_resp.json()["version"]["id"]

    format_resp = test_client.post(
        f"/api/v1/datasets/{dataset_id}/versions/{dataset_version_id}/formats/run",
        headers=_auth_header(owner),
    )
    dataset_format_version_id = format_resp.json()[0]["id"]

    monkeypatch.setattr(settings, "max_training_gpus", 2)

    response = test_client.post(
        "/api/v1/training/jobs",
        json={
            "workspace_id": workspace.id,
            "dataset_version_id": dataset_version_id,
            "dataset_format_version_id": dataset_format_version_id,
            "training_template_id": template_id,
            "requested_gpus": 5,
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 422
    assert "最多支持" in response.json()["detail"]

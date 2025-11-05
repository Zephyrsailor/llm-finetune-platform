"""Training monitoring API tests."""

from __future__ import annotations

from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from backend.tests.test_training_wizard import _prepare_dataset_resources

pytest_plugins = ["backend.tests.test_datasets"]


def _create_alert_rule(
    test_client: TestClient,
    owner,
    workspace_id: int,
    metric: str = "loss",
    operator: str = "gt",
    threshold: float = 0.9,
    cooldown_seconds: int = 60,
) -> dict:
    response = test_client.post(
        "/api/v1/training/monitor/alert-rules",
        json={
            "workspace_id": workspace_id,
            "name": "loss-above-threshold",
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "cooldown_seconds": cooldown_seconds,
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_training_job(
    test_client: TestClient,
    engine,
    owner,
    workspace_id: int,
    dataset_version_id: int,
    dataset_format_version_id: int,
    template_id: int,
) -> dict:
    response = test_client.post(
        "/api/v1/training/jobs",
        json={
            "workspace_id": workspace_id,
            "dataset_version_id": dataset_version_id,
            "dataset_format_version_id": dataset_format_version_id,
            "training_template_id": template_id,
            "params": {"learning_rate": 2e-4},
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_training_monitoring_alert_flow(client: Tuple[TestClient, Session]):
    test_client, engine = client
    owner = _create_user(engine, "monitor@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Monitor Lab")

    # Prepare dataset and format resources for training job
    dataset_version_id, dataset_format_version_id = _prepare_dataset_resources(
        test_client, engine, owner, workspace.id
    )

    # Retrieve template id
    templates_resp = test_client.get(
        "/api/v1/training/templates",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert templates_resp.status_code == 200
    template_id = templates_resp.json()[0]["id"]

    # Create alert rule before launching training job
    _create_alert_rule(test_client, owner, workspace.id, threshold=0.6)

    # Launch training job (Celery eager executes synchronously)
    job_payload = _create_training_job(
        test_client,
        engine,
        owner,
        workspace.id,
        dataset_version_id,
        dataset_format_version_id,
        template_id,
    )

    # fetch latest run id
    job_id = job_payload["id"]
    job_resp = test_client.get(
        f"/api/v1/training/jobs/{job_id}",
        headers=_auth_header(owner),
    )
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    run_id = job_data["latest_run"]["id"]

    # Metrics endpoint returns samples
    metrics_resp = test_client.get(
        f"/api/v1/training/monitor/runs/{run_id}/metrics",
        headers=_auth_header(owner),
    )
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert any(sample["metric"] == "loss" for sample in metrics)

    # Alerts endpoint should contain triggered alert
    alerts_resp = test_client.get(
        "/api/v1/training/monitor/alerts",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) >= 1
    alert_id = alerts[0]["id"]

    # Update alert status to acknowledged
    status_resp = test_client.post(
        f"/api/v1/training/monitor/alerts/{alert_id}/status",
        json={"status": "acknowledged", "notes": "Investigating"},
        headers=_auth_header(owner),
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "acknowledged"

    # Export metrics
    export_metrics = test_client.get(
        "/api/v1/training/monitor/metrics/export",
        params={"run_id": run_id},
        headers=_auth_header(owner),
    )
    assert export_metrics.status_code == 200
    assert export_metrics.content.startswith(b"run_id")

    # Export alerts
    export_alerts = test_client.get(
        "/api/v1/training/monitor/alerts/export",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert export_alerts.status_code == 200
    assert export_alerts.content.startswith(b"alert_id")

    # Verify list runs aggregates metrics and alerts
    runs_resp = test_client.get(
        "/api/v1/training/monitor/runs",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert any(r["run_id"] == run_id for r in runs)

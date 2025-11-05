"""Runtime monitoring API tests."""

from __future__ import annotations

from typing import Tuple

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from backend.tests.test_inference import _bootstrap_active_deployment
from app.models import InferenceCallStatus
from app.repositories.inference import InferenceCallRepository

pytest_plugins = ["backend.tests.test_datasets"]


def test_runtime_monitor_overview_and_alert_flow(client: Tuple[TestClient, Session]) -> None:
    test_client, engine = client
    owner = _create_user(engine, "runtime-observer@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Runtime Lab")

    with Session(engine) as session:
        deployment_id, model_version_id = _bootstrap_active_deployment(session, workspace.id, owner)

    # Generate successful inference calls
    for message in ["早上好", "测试请求", "监控样本"]:
        response = test_client.post(
            "/api/v1/inference",
            json={
                "workspace_id": workspace.id,
                "deployment_id": deployment_id,
                "inputs": [message],
            },
            headers=_auth_header(owner),
        )
        assert response.status_code == 200, response.text

    # Insert a rate-limited call to trigger error-related alerts
    with Session(engine) as session:
        repo = InferenceCallRepository(session)
        repo.create(
            workspace_id=workspace.id,
            project_id=None,
            deployment_id=deployment_id,
            model_version_id=model_version_id,
            api_key_id=None,
            user_id=owner.id,
            request_payload={"inputs": ["触发限流"]},
            response_payload=None,
            status=InferenceCallStatus.RATE_LIMITED,
            latency_ms=180,
            input_tokens=12,
            output_tokens=0,
            error_message="rate limited for test",
        )
        session.commit()

    create_rule_resp = test_client.post(
        "/api/v1/runtime/monitor/alert-rules",
        json={
            "workspace_id": workspace.id,
            "deployment_id": deployment_id,
            "name": "error-rate-watch",
            "metric": "error_rate",
            "operator": "gte",
            "threshold": 0.2,
            "cooldown_seconds": 30,
        },
        headers=_auth_header(owner),
    )
    assert create_rule_resp.status_code == 201, create_rule_resp.text
    rule_payload = create_rule_resp.json()

    overview_resp = test_client.get(
        "/api/v1/runtime/monitor/overview",
        params={"workspace_id": workspace.id, "window_minutes": 60},
        headers=_auth_header(owner),
    )
    assert overview_resp.status_code == 200, overview_resp.text
    overview = overview_resp.json()

    metrics = overview["metrics"]
    assert metrics["total_calls"] >= 4
    assert metrics["error_rate"] > 0
    assert any(item["deployment_id"] == deployment_id for item in overview["per_deployment"])
    assert overview["resource_usage"], "resource usage should be present"
    first_resource = overview["resource_usage"][0]
    assert "gpu_memory_mb" in first_resource["metrics"]
    assert first_resource["status"] in {"deploying", "active", "failed", "rolled_back", "pending"}

    alerts = overview["alerts"]
    assert alerts, "alert should be triggered for elevated error rate"
    assert alerts[0]["recommendation"]
    alert_id = alerts[0]["id"]

    list_alerts_resp = test_client.get(
        "/api/v1/runtime/monitor/alerts",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_alerts_resp.status_code == 200
    assert any(item["id"] == alert_id for item in list_alerts_resp.json())

    status_resp = test_client.post(
        f"/api/v1/runtime/monitor/alerts/{alert_id}/status",
        json={"status": "acknowledged", "notes": "正在调查"},
        headers=_auth_header(owner),
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["status"] == "acknowledged"

    update_rule_resp = test_client.patch(
        f"/api/v1/runtime/monitor/alert-rules/{rule_payload['id']}",
        json={"is_active": False},
        headers=_auth_header(owner),
    )
    assert update_rule_resp.status_code == 200
    assert update_rule_resp.json()["is_active"] is False

    list_rules_resp = test_client.get(
        "/api/v1/runtime/monitor/alert-rules",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_rules_resp.status_code == 200
    assert any(rule["id"] == rule_payload["id"] for rule in list_rules_resp.json())

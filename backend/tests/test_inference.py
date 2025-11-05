"""Inference API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.tests.test_datasets import (
    _auth_header,
    _create_user,
    _create_workspace_via_api,
)
from backend.tests.test_deployments import _create_passed_evaluation
from app.core.config import settings
from app.repositories.role import RoleRepository
from app.services.roles import RoleOperation
from app.services.model_registry import ModelRegistryService
from app.services.deployment import DeploymentService
from app.models import ModelVersionStatus

pytest_plugins = ["backend.tests.test_datasets"]


def _bootstrap_active_deployment(session: Session, workspace_id: int, owner):
    registry = ModelRegistryService(session)
    model = registry.create_model(
        workspace_id=workspace_id,
        project_id=None,
        name="chat-model",
        description="",
        base_model="llama-3-8b",
        tags=["sdk"],
        current_user=owner,
        ip_address=None,
        user_agent=None,
    )
    evaluation_job = _create_passed_evaluation(session, workspace_id, owner.id)
    version = registry.create_version(
        model_id=model["id"],
        current_user=owner,
        training_run_id=None,
        evaluation_job_id=evaluation_job.id,
        metadata=None,
        notes="initial candidate",
        deployment_target=None,
        artifact_path=None,
        ip_address=None,
        user_agent=None,
    )
    registry.update_version_status(
        model_id=model["id"],
        version_id=version["id"],
        target_status=ModelVersionStatus.PRODUCTION,
        notes="prod-ready",
        deployment_target="infra-a",
        current_user=owner,
        ip_address=None,
        user_agent=None,
    )
    service = DeploymentService(session)
    deployment = service.create_deployment(
        workspace_id=workspace_id,
        project_id=None,
        model_version_id=version["id"],
        environment="production",
        config={"replicas": 1},
        notes="initial deployment",
        current_user=owner,
        ip_address=None,
        user_agent=None,
    )
    return deployment["id"], version["id"]


def test_inference_invocation_with_user(client):
    test_client, engine = client
    owner = _create_user(engine, "inference-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Inference Lab")

    with Session(engine) as session:
        deployment_id, _ = _bootstrap_active_deployment(session, workspace.id, owner)
        operations = RoleRepository(session).list_operations_for_member(
            workspace_id=workspace.id,
            user_id=owner.id,
        )
        assert RoleOperation.INFERENCE_USE.value in operations

    response = test_client.post(
        "/api/v1/inference",
        json={
            "workspace_id": workspace.id,
            "deployment_id": deployment_id,
            "inputs": ["你好，今天的工作安排是？"],
        },
        headers=_auth_header(owner),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["outputs"]
    assert payload["deployment_id"] == deployment_id

    logs = test_client.get(
        "/api/v1/inference/logs",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert logs.status_code == 200, logs.text
    log_payload = logs.json()
    assert log_payload["logs"]

    detail = test_client.get(
        f"/api/v1/inference/calls/{payload['call_id']}",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert detail.status_code == 200


def test_inference_rate_limit_enforced(client):
    test_client, engine = client
    owner = _create_user(engine, "rate-limit@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Rate Lab")

    with Session(engine) as session:
        deployment_id, _ = _bootstrap_active_deployment(session, workspace.id, owner)

    original_limit = settings.inference_rate_limit_per_minute
    original_quota = settings.inference_daily_quota
    settings.inference_rate_limit_per_minute = 1
    settings.inference_daily_quota = 2
    try:
        first = test_client.post(
            "/api/v1/inference",
            json={
                "workspace_id": workspace.id,
                "deployment_id": deployment_id,
                "inputs": ["hello world"],
            },
            headers=_auth_header(owner),
        )
        assert first.status_code == 200, first.text

        second = test_client.post(
            "/api/v1/inference",
            json={
                "workspace_id": workspace.id,
                "deployment_id": deployment_id,
                "inputs": ["第二次调用"],
            },
            headers=_auth_header(owner),
        )
        assert second.status_code == 429, second.text
    finally:
        settings.inference_rate_limit_per_minute = original_limit
        settings.inference_daily_quota = original_quota
    logs = test_client.get(
        "/api/v1/inference/logs",
        params={"workspace_id": workspace.id, "limit": 5},
        headers=_auth_header(owner),
    )
    assert logs.status_code == 200
    statuses = {entry["status"] for entry in logs.json()["logs"]}
    assert "rate_limited" in statuses


def test_inference_with_api_key(client):
    test_client, engine = client
    owner = _create_user(engine, "sdk-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="SDK Lab")

    with Session(engine) as session:
        deployment_id, _ = _bootstrap_active_deployment(session, workspace.id, owner)

    create_resp = test_client.post(
        "/api/v1/inference/api-keys",
        json={"workspace_id": workspace.id, "name": "integration-key"},
        headers=_auth_header(owner),
    )
    assert create_resp.status_code == 201, create_resp.text
    key_data = create_resp.json()
    api_key_secret = key_data["secret"]

    invoke = test_client.post(
        "/api/v1/inference",
            json={
                "workspace_id": workspace.id,
                "deployment_id": deployment_id,
                "inputs": ["API Key call"],
            },
        headers={"X-LLMFT-API-Key": api_key_secret},
    )
    assert invoke.status_code == 200, invoke.text
    assert invoke.json()["outputs"]

    list_resp = test_client.get(
        "/api/v1/inference/api-keys",
        params={"workspace_id": workspace.id},
        headers=_auth_header(owner),
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["is_active"] is True


def test_grpc_inference_invocation(client):
    struct_pb2 = pytest.importorskip("google.protobuf.struct_pb2")
    from app.grpc.inference_server import InferenceGrpcHandler  # noqa: WPS433 (import inside test)

    test_client, engine = client
    owner = _create_user(engine, "grpc-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="gRPC Lab")

    with Session(engine) as session:
        deployment_id, _ = _bootstrap_active_deployment(session, workspace.id, owner)

    key_resp = test_client.post(
        "/api/v1/inference/api-keys",
        json={"workspace_id": workspace.id, "name": "grpc"},
        headers=_auth_header(owner),
    )
    assert key_resp.status_code == 201, key_resp.text
    secret = key_resp.json()["secret"]

    request_struct = struct_pb2.Struct()
    request_struct.update(
        {
            "workspace_id": workspace.id,
            "deployment_id": deployment_id,
            "inputs": ["grpc 调用"],
            "parameters": {"temperature": "0.2"},
        }
    )

    class _StubContext:
        def __init__(self, metadata):
            self._metadata = metadata

        def invocation_metadata(self):
            return self._metadata

        def abort(self, code, details):
            raise RuntimeError((code, details))

    handler = InferenceGrpcHandler(lambda: Session(engine))
    response = handler.invoke(request_struct, _StubContext([("x-llmft-api-key", secret)]))
    assert response["outputs"]
    assert response["deployment_id"] == deployment_id

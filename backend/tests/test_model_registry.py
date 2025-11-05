"""Model registry service tests."""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session

from backend.tests.test_datasets import (
    _create_user,
    _create_workspace_via_api,
)
from app.models import (
    EvaluationJob,
    EvaluationJobStatus,
    EvaluationTaskType,
    EvaluationTemplate,
    ModelVersionStatus,
)
from app.services.model_registry import ModelRegistryService
from app.services.errors import ModelVersionPromotionError

pytest_plugins = ["backend.tests.test_datasets"]


def _create_evaluation_template(session: Session, workspace_id: int) -> EvaluationTemplate:
    template = EvaluationTemplate(
        key=f"registry-{uuid.uuid4()}",
        name="Registry Gate Template",
        description=None,
        task_type=EvaluationTaskType.QA,
        metrics=["overall_score"],
        config_json={},
        workspace_id=workspace_id,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def _create_evaluation_job(
    session: Session,
    *,
    workspace_id: int,
    template_id: int,
    created_by: int | None,
    metrics: dict,
) -> EvaluationJob:
    job = EvaluationJob(
        workspace_id=workspace_id,
        project_id=None,
        training_run_id=None,
        evaluation_template_id=template_id,
        status=EvaluationJobStatus.COMPLETED,
        metrics_json=metrics,
        report_path="evaluations/report.md",
        created_by=created_by,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_model_registry_flow(client):
    test_client, engine = client
    owner = _create_user(engine, "registry-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Registry Workspace")

    with Session(engine) as session:
        service = ModelRegistryService(session)

        model_payload = service.create_model(
            workspace_id=workspace.id,
            project_id=None,
            name="chat-model",
            description="测试模型",
            base_model="llama-3-8b",
            tags=["release", "chat"],
            current_user=owner,
            ip_address=None,
            user_agent=None,
        )
        assert model_payload["name"] == "chat-model"
        model_id = model_payload["id"]

        template = _create_evaluation_template(session, workspace.id)
        passing_job = _create_evaluation_job(
            session,
            workspace_id=workspace.id,
            template_id=template.id,
            created_by=owner.id,
            metrics={"thresholds": {"overall": {"triggered": False}}},
        )

        version_payload = service.create_version(
            model_id=model_id,
            current_user=owner,
            training_run_id=None,
            evaluation_job_id=passing_job.id,
            metadata={"summary": {"notes": "first candidate"}},
            notes="候选版本",
            deployment_target=None,
            artifact_path=None,
            ip_address=None,
            user_agent=None,
        )
        assert version_payload["version"] == 1
        version_id = version_payload["id"]

        promoted = service.update_version_status(
            model_id=model_id,
            version_id=version_id,
            target_status=ModelVersionStatus.PRODUCTION,
            notes=version_payload["notes"],
            deployment_target="prod-default",
            current_user=owner,
            ip_address=None,
            user_agent=None,
        )
        assert promoted["status"] == ModelVersionStatus.PRODUCTION.value

        failing_job = _create_evaluation_job(
            session,
            workspace_id=workspace.id,
            template_id=template.id,
            created_by=owner.id,
            metrics={"thresholds": {"overall": {"triggered": True}}},
        )

        failing_version = service.create_version(
            model_id=model_id,
            current_user=owner,
            training_run_id=None,
            evaluation_job_id=failing_job.id,
            metadata=None,
            notes=None,
            deployment_target=None,
            artifact_path=None,
            ip_address=None,
            user_agent=None,
        )

        with pytest.raises(ModelVersionPromotionError):
            service.update_version_status(
                model_id=model_id,
                version_id=failing_version["id"],
                target_status=ModelVersionStatus.PRODUCTION,
                notes=None,
                deployment_target=None,
                current_user=owner,
                ip_address=None,
                user_agent=None,
            )

    models_list = service.list_models(
        workspace_id=workspace.id,
        project_id=None,
        status=None,
        current_user=owner,
    )
    assert len(models_list) == 1
    statuses = {item["status"] for item in models_list[0]["versions"]}
    assert ModelVersionStatus.PRODUCTION.value in statuses

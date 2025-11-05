"""Deployment service tests."""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from backend.tests.test_datasets import (
    _create_user,
    _create_workspace_via_api,
)
from app.models import (
    DeploymentStatus,
    EvaluationJob,
    EvaluationJobStatus,
    EvaluationTaskType,
    EvaluationTemplate,
    ModelVersionStatus,
)
from app.services.model_registry import ModelRegistryService
from app.services.deployment import DeploymentService
from app.services.errors import ModelVersionPromotionError

pytest_plugins = ["backend.tests.test_datasets"]


def _create_passed_evaluation(session: Session, workspace_id: int, created_by: int | None) -> EvaluationJob:
    template = session.exec(
        select(EvaluationTemplate).where(EvaluationTemplate.key == "qa-default")
    ).first()
    if template is None:
        template = EvaluationTemplate(
            key="qa-default",
            name="默认问答模板",
            description=None,
            task_type=EvaluationTaskType.QA,
            metrics=["accuracy"],
            config_json={},
            is_builtin=True,
            workspace_id=None,
        )
        session.add(template)
        session.commit()
        session.refresh(template)

    job = EvaluationJob(
        workspace_id=workspace_id,
        project_id=None,
        training_run_id=None,
        evaluation_template_id=template.id,
        status=EvaluationJobStatus.COMPLETED,
        metrics_json={"thresholds": {"overall": {"triggered": False}}},
        report_path="storage/reports/placeholder.md",
        created_by=created_by,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_successful_deployment(client):
    test_client, engine = client
    owner = _create_user(engine, "deploy-owner@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Deploy Lab")

    with Session(engine) as session:
        registry = ModelRegistryService(session)

        model = registry.create_model(
            workspace_id=workspace.id,
            project_id=None,
            name="chat-model",
            description="",
            base_model="llama-3-8b",
            tags=["deploy"],
            current_user=owner,
            ip_address=None,
            user_agent=None,
        )

        evaluation_job = _create_passed_evaluation(session, workspace.id, owner.id)
        version = registry.create_version(
            model_id=model["id"],
            current_user=owner,
            training_run_id=None,
            evaluation_job_id=evaluation_job.id,
            metadata=None,
            notes="候选版本",
            deployment_target=None,
            artifact_path=None,
            ip_address=None,
            user_agent=None,
        )
        registry.update_version_status(
            model_id=model["id"],
            version_id=version["id"],
            target_status=ModelVersionStatus.PRODUCTION,
            notes="生产版本",
            deployment_target="infra-a",
            current_user=owner,
            ip_address=None,
            user_agent=None,
        )

        service = DeploymentService(session)
        deployment = service.create_deployment(
            workspace_id=workspace.id,
            project_id=None,
            model_version_id=version["id"],
            environment="production",
            config={"replicas": 1},
            notes="首次部署",
            current_user=owner,
            ip_address=None,
            user_agent=None,
    )

        result = service.get_deployment(deployment["id"], current_user=owner)
        assert result["status"] == DeploymentStatus.ACTIVE.value
        assert result["endpoint_url"]
        assert result["events"]
        instances = result["instances"]
        assert instances and instances[0]["status"] == DeploymentStatus.ACTIVE.value
        assert instances[0]["endpoint_url"]


def test_deployment_blocked_for_non_production_version(client):
    test_client, engine = client
    owner = _create_user(engine, "deploy-block@example.com")
    workspace = _create_workspace_via_api(test_client, engine, owner, name="Deploy Block")

    with Session(engine) as session:
        registry = ModelRegistryService(session)
        model = registry.create_model(
            workspace_id=workspace.id,
            project_id=None,
            name="draft-model",
            description="",
            base_model="llama-3-8b",
            tags=[],
            current_user=owner,
            ip_address=None,
            user_agent=None,
        )

        evaluation_job = _create_passed_evaluation(session, workspace.id, owner.id)
        version = registry.create_version(
            model_id=model["id"],
            current_user=owner,
            training_run_id=None,
            evaluation_job_id=evaluation_job.id,
            metadata=None,
            notes="候选版本",
            deployment_target=None,
            artifact_path=None,
            ip_address=None,
            user_agent=None,
        )

        service = DeploymentService(session)
        with pytest.raises(ModelVersionPromotionError):
            service.create_deployment(
                workspace_id=workspace.id,
                project_id=None,
                model_version_id=version["id"],
                environment="prod",
                config={},
                notes=None,
                current_user=owner,
                ip_address=None,
                user_agent=None,
            )

"""Celery tasks driving deployment lifecycle."""

from __future__ import annotations

from time import sleep

from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.database import engine
from app.services.deployment import DeploymentService
from app.models import DeploymentStatus


@celery_app.task(name="deployment.run_deployment")
def run_deployment_job(deployment_id: int) -> None:
    """Simulate deploying a model version to vLLM."""
    with Session(engine) as session:
        service = DeploymentService(session)
        deployment = service._deployments.get(deployment_id)  # type: ignore[attr-defined]
        if deployment is None:
            return
        service.mark_deployment_status(
            deployment_id,
            status=DeploymentStatus.DEPLOYING,
            event_type="deployment.deploying",
            message="开始启动 vLLM 服务，准备加载模型。",
            payload=None,
        )
        # Simulate build / start time
        sleep(0.1)
        run_deployment_health_check.delay(deployment_id)


@celery_app.task(name="deployment.health_check")
def run_deployment_health_check(deployment_id: int) -> None:
    """Simulate a health check request."""
    with Session(engine) as session:
        service = DeploymentService(session)
        deployment = service._deployments.get(deployment_id)  # type: ignore[attr-defined]
        if deployment is None:
            return
        endpoint_url = service.build_endpoint(deployment.model_version_id, deployment.environment)
        token = service.generate_access_token()
        metrics = {
            "latency_p95_ms": 120,
            "throughput_rps": 45,
            "error_rate": 0.0,
            "gpu_memory_mb": 14336,
            "gpu_utilization": 0.68,
        }
        service.finalize_success(
            deployment_id,
            endpoint_url=endpoint_url,
            access_token=token,
            metrics=metrics,
        )


@celery_app.task(name="deployment.rollback")
def run_deployment_rollback(deployment_id: int, reason: str) -> None:
    """Simulate rollback workflow."""
    with Session(engine) as session:
        service = DeploymentService(session)
        service.mark_rolled_back(deployment_id, reason=reason)

"""Training monitoring and alert endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    get_current_user,
    get_training_monitoring_service,
)
from app.schemas.training_monitoring import (
    TrainingAlertResponse,
    TrainingAlertRuleCreateRequest,
    TrainingAlertRuleResponse,
    TrainingAlertRuleUpdateRequest,
    TrainingAlertStatusUpdateRequest,
    TrainingMetricSampleResponse,
    TrainingMonitorRunResponse,
)
from app.services.training_monitoring import TrainingMonitoringService
from app.models import User


router = APIRouter(prefix="/v1/training/monitor", tags=["training-monitor"])


@router.get(
    "/runs",
    response_model=list[TrainingMonitorRunResponse],
)
async def list_training_runs(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> list[TrainingMonitorRunResponse]:
    service.ensure_can_view(workspace_id, current_user)
    runs = service.list_runs(workspace_id)
    results: list[TrainingMonitorRunResponse] = []
    for run in runs:
        job = run.job or service.get_job(run.job_id)
        latest_metrics_map = service.latest_metrics_for_run(run.id)
        latest_metrics = [
            TrainingMetricSampleResponse.model_validate(sample, from_attributes=True)
            for sample in latest_metrics_map.values()
            if sample is not None
        ]
        alerts = [
            TrainingAlertResponse.model_validate(alert, from_attributes=True)
            for alert in service.list_alerts_for_run(run.id)
        ]
        latest_evaluation = None
        metadata = run.metadata_json or {}
        if isinstance(metadata, dict):
            evaluation_section = metadata.get("evaluation") or {}
            metrics = evaluation_section.get("latest_metrics")
            if metrics:
                latest_evaluation = {
                    "job_id": evaluation_section.get("latest_job_id"),
                    "metrics": metrics,
                    "updated_at": evaluation_section.get("updated_at"),
                }
        results.append(
            TrainingMonitorRunResponse(
                run_id=run.id,
                job_id=run.job_id,
                workspace_id=job.workspace_id if job else workspace_id,
                project_id=job.project_id if job else None,
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                job_error_message=job.error_message if job else None,
                latest_metrics=latest_metrics,
                alerts=alerts,
                latest_evaluation=latest_evaluation,
            )
        )
    return results


@router.get(
    "/runs/{run_id}/metrics",
    response_model=list[TrainingMetricSampleResponse],
)
async def list_run_metrics(
    run_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> list[TrainingMetricSampleResponse]:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练运行不存在")
    job = service.get_job(run.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联训练任务不存在")
    service.ensure_can_view(job.workspace_id, current_user)
    samples = service.list_metric_samples(run_id)
    return [
        TrainingMetricSampleResponse.model_validate(sample, from_attributes=True) for sample in samples
    ]


@router.post(
    "/alert-rules",
    response_model=TrainingAlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule(
    payload: TrainingAlertRuleCreateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> TrainingAlertRuleResponse:
    rule = service.create_alert_rule(
        workspace_id=payload.workspace_id,
        name=payload.name,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        cooldown_seconds=payload.cooldown_seconds,
        channels=payload.channels,
        current_user=current_user,
    )
    return TrainingAlertRuleResponse.model_validate(rule, from_attributes=True)


@router.get(
    "/alert-rules",
    response_model=list[TrainingAlertRuleResponse],
)
async def list_alert_rules(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> list[TrainingAlertRuleResponse]:
    service.ensure_can_view(workspace_id, current_user)
    rules = service.list_alert_rules(workspace_id)
    return [TrainingAlertRuleResponse.model_validate(rule, from_attributes=True) for rule in rules]


@router.patch(
    "/alert-rules/{rule_id}",
    response_model=TrainingAlertRuleResponse,
)
async def update_alert_rule(
    rule_id: int,
    payload: TrainingAlertRuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> TrainingAlertRuleResponse:
    rule = service.get_alert_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警规则不存在")
    updated = service.update_alert_rule(
        rule=rule,
        name=payload.name,
        operator=payload.operator,
        threshold=payload.threshold,
        cooldown_seconds=payload.cooldown_seconds,
        is_active=payload.is_active,
        channels=payload.channels,
        current_user=current_user,
    )
    return TrainingAlertRuleResponse.model_validate(updated, from_attributes=True)


@router.post(
    "/alerts/{alert_id}/status",
    response_model=TrainingAlertResponse,
)
async def update_alert_status(
    alert_id: int,
    payload: TrainingAlertStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> TrainingAlertResponse:
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    updated = service.update_alert_status(
        alert=alert,
        status=payload.status,
        notes=payload.notes,
        current_user=current_user,
    )
    return TrainingAlertResponse.model_validate(updated, from_attributes=True)


@router.get(
    "/alerts",
    response_model=list[TrainingAlertResponse],
)
async def list_alerts(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> list[TrainingAlertResponse]:
    service.ensure_can_view(workspace_id, current_user)
    alerts = service.list_alerts_for_workspace(workspace_id)
    return [TrainingAlertResponse.model_validate(alert, from_attributes=True) for alert in alerts]


@router.get("/metrics/export")
async def export_metrics(
    run_id: int = Query(..., description="训练运行 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> Response:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练运行不存在")
    job = service.get_job(run.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联训练任务不存在")
    service.ensure_can_view(job.workspace_id, current_user)
    content = service.export_metrics_csv(run_id)
    filename = f"training-metrics-run-{run_id}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alerts/export")
async def export_alerts(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingMonitoringService = Depends(get_training_monitoring_service),
) -> Response:
    service.ensure_can_view(workspace_id, current_user)
    content = service.export_alerts_csv(workspace_id)
    filename = f"training-alerts-workspace-{workspace_id}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

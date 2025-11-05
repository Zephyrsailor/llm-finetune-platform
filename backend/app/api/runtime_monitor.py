"""Runtime monitoring API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_runtime_monitoring_service,
)
from app.schemas.runtime_monitoring import (
    RuntimeAlertResponse,
    RuntimeAlertRuleCreateRequest,
    RuntimeAlertRuleResponse,
    RuntimeAlertRuleUpdateRequest,
    RuntimeAlertStatusUpdateRequest,
    RuntimeOverviewResponse,
)
from app.services.runtime_monitoring import RuntimeMonitoringService
from app.models import User


router = APIRouter(prefix="/v1/runtime/monitor", tags=["runtime-monitor"])


@router.get(
    "/overview",
    response_model=RuntimeOverviewResponse,
)
async def get_runtime_overview(
    workspace_id: int = Query(..., description="工作空间 ID"),
    window_minutes: int = Query(15, ge=1, le=1440),
    deployment_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> RuntimeOverviewResponse:
    payload = service.get_overview(
        workspace_id=workspace_id,
        current_user=current_user,
        window_minutes=window_minutes,
        deployment_id=deployment_id,
    )
    return RuntimeOverviewResponse.model_validate(payload)


@router.get(
    "/alert-rules",
    response_model=list[RuntimeAlertRuleResponse],
)
async def list_runtime_alert_rules(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> list[RuntimeAlertRuleResponse]:
    rules = service.list_alert_rules(workspace_id=workspace_id, current_user=current_user)
    return [RuntimeAlertRuleResponse.model_validate(rule) for rule in rules]


@router.post(
    "/alert-rules",
    response_model=RuntimeAlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_runtime_alert_rule(
    payload: RuntimeAlertRuleCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> RuntimeAlertRuleResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    result = service.create_alert_rule(
        workspace_id=payload.workspace_id,
        deployment_id=payload.deployment_id,
        name=payload.name,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        cooldown_seconds=payload.cooldown_seconds,
        channels=payload.channels,
        current_user=current_user,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return RuntimeAlertRuleResponse.model_validate(result)


@router.patch(
    "/alert-rules/{rule_id}",
    response_model=RuntimeAlertRuleResponse,
)
async def update_runtime_alert_rule(
    rule_id: int,
    payload: RuntimeAlertRuleUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> RuntimeAlertRuleResponse:
    rule = service.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警规则不存在")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    result = service.update_alert_rule(
        rule=rule,
        name=payload.name,
        operator=payload.operator,
        threshold=payload.threshold,
        cooldown_seconds=payload.cooldown_seconds,
        is_active=payload.is_active,
        channels=payload.channels,
        deployment_id=payload.deployment_id,
        current_user=current_user,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return RuntimeAlertRuleResponse.model_validate(result)


@router.get(
    "/alerts",
    response_model=list[RuntimeAlertResponse],
)
async def list_runtime_alerts(
    workspace_id: int = Query(..., description="工作空间 ID"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> list[RuntimeAlertResponse]:
    alerts = service.list_alerts(workspace_id=workspace_id, current_user=current_user, limit=limit)
    return [RuntimeAlertResponse.model_validate(alert) for alert in alerts]


@router.post(
    "/alerts/{alert_id}/status",
    response_model=RuntimeAlertResponse,
)
async def update_runtime_alert_status(
    alert_id: int,
    payload: RuntimeAlertStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RuntimeMonitoringService = Depends(get_runtime_monitoring_service),
) -> RuntimeAlertResponse:
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    updated = service.update_alert_status(
        alert=alert,
        status=payload.status,
        notes=payload.notes,
        current_user=current_user,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return RuntimeAlertResponse.model_validate(updated)

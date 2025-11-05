"""Deployment API endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_deployment_service
from app.models import DeploymentStatus, User
from app.schemas.deployment import (
    DeploymentCreateRequest,
    DeploymentResponse,
    DeploymentListResponse,
    DeploymentTrafficUpdateRequest,
    DeploymentRollbackRequest,
)
from app.services.deployment import DeploymentService
from app.services.errors import (
    AccessDeniedError,
    ModelRegistryError,
    ModelVersionPromotionError,
    WorkspaceNotFoundError,
    ProjectNotFoundError,
)

router = APIRouter(prefix="/v1/deployments", tags=["deployments"])


@router.get(
    "",
    response_model=DeploymentListResponse,
)
async def list_deployments(
    workspace_id: int = Query(..., description="工作空间 ID"),
    project_id: int | None = Query(None, description="项目 ID"),
    status_filter: DeploymentStatus | None = Query(None, alias="status", description="部署状态筛选"),
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service),
) -> DeploymentListResponse:
    try:
        deployments = service.list_deployments(
            workspace_id=workspace_id,
            project_id=project_id,
            status=status_filter,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentListResponse(deployments=deployments)


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    payload: DeploymentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service),
) -> DeploymentResponse:
    try:
        deployment = service.create_deployment(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            model_version_id=payload.model_version_id,
            environment=payload.environment,
            config={
                "replicas": payload.replicas,
                "max_batch_size": payload.max_batch_size,
                "max_concurrency": payload.max_concurrency,
            },
            notes=payload.notes,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except (
        WorkspaceNotFoundError,
        ProjectNotFoundError,
        ModelRegistryError,
        ModelVersionPromotionError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentResponse.model_validate(deployment)


@router.get(
    "/{deployment_id}",
    response_model=DeploymentResponse,
)
async def get_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service),
) -> DeploymentResponse:
    try:
        payload = service.get_deployment(deployment_id, current_user=current_user)
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentResponse.model_validate(payload)


@router.post(
    "/{deployment_id}/traffic",
    response_model=DeploymentResponse,
)
async def update_deployment_traffic(
    deployment_id: int,
    payload: DeploymentTrafficUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service),
) -> DeploymentResponse:
    try:
        updated = service.update_traffic(
            deployment_id=deployment_id,
            traffic_percent=payload.traffic_percent,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except (ModelRegistryError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentResponse.model_validate(updated)


@router.post(
    "/{deployment_id}/rollback",
    response_model=DeploymentResponse,
)
async def rollback_deployment(
    deployment_id: int,
    payload: DeploymentRollbackRequest,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service),
) -> DeploymentResponse:
    try:
        updated = service.rollback(
            deployment_id=deployment_id,
            reason=payload.reason,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeploymentResponse.model_validate(updated)

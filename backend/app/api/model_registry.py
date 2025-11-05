"""Model registry API endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_model_registry_service
from app.models import ModelVersionStatus, User
from app.schemas.model_registry import (
    ModelCreateRequest,
    ModelResponse,
    ModelVersionCreateRequest,
    ModelVersionResponse,
    ModelVersionStatusUpdateRequest,
    ModelVersionExportResponse,
)
from app.services.errors import (
    AccessDeniedError,
    ModelRegistryError,
    ModelVersionPromotionError,
    ProjectNotFoundError,
    TrainingJobError,
    WorkspaceNotFoundError,
)
from app.services.model_registry import ModelRegistryService

router = APIRouter(prefix="/v1/models", tags=["model-registry"])


@router.get(
    "",
    response_model=List[ModelResponse],
)
async def list_registered_models(
    workspace_id: int = Query(..., description="工作空间 ID"),
    project_id: int | None = Query(None, description="项目 ID，可选"),
    status: ModelVersionStatus | None = Query(None, description="筛选模型版本状态"),
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> list[ModelResponse]:
    try:
        models = service.list_models(
            workspace_id=workspace_id,
            project_id=project_id,
            status=status,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [ModelResponse.model_validate(model) for model in models]


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
)
async def get_registered_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> ModelResponse:
    try:
        model = service.get_model(model_id, current_user=current_user)
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ModelResponse.model_validate(model)


@router.post(
    "",
    response_model=ModelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registered_model(
    payload: ModelCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> ModelResponse:
    try:
        model = service.create_model(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            base_model=payload.base_model,
            tags=payload.tags,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except (
        WorkspaceNotFoundError,
        ProjectNotFoundError,
        ModelRegistryError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ModelResponse.model_validate(model)


@router.post(
    "/{model_id}/versions",
    response_model=ModelVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_model_version(
    model_id: int,
    payload: ModelVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> ModelVersionResponse:
    try:
        version = service.create_version(
            model_id=model_id,
            current_user=current_user,
            training_run_id=payload.training_run_id,
            evaluation_job_id=payload.evaluation_job_id,
            metadata=payload.metadata,
            notes=payload.notes,
            deployment_target=payload.deployment_target,
            artifact_path=payload.artifact_path,
            ip_address=None,
            user_agent=None,
        )
    except (
        ModelRegistryError,
        TrainingJobError,
        WorkspaceNotFoundError,
        ProjectNotFoundError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ModelVersionResponse.model_validate(version)


@router.patch(
    "/{model_id}/versions/{version_id}",
    response_model=ModelVersionResponse,
)
async def update_model_version_status(
    model_id: int,
    version_id: int,
    payload: ModelVersionStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> ModelVersionResponse:
    try:
        version = service.update_version_status(
            model_id=model_id,
            version_id=version_id,
            target_status=payload.status,
            notes=payload.notes,
            deployment_target=payload.deployment_target,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
    except ModelVersionPromotionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ModelVersionResponse.model_validate(version)


@router.post(
    "/{model_id}/versions/{version_id}:export",
    response_model=ModelVersionExportResponse,
)
async def export_model_version(
    model_id: int,
    version_id: int,
    export_format: str = Query("json", description="导出格式（json 或 markdown）"),
    current_user: User = Depends(get_current_user),
    service: ModelRegistryService = Depends(get_model_registry_service),
) -> ModelVersionExportResponse:
    try:
        result = service.export_version_metadata(
            model_id=model_id,
            version_id=version_id,
            export_format=export_format,
            current_user=current_user,
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ModelVersionExportResponse.model_validate(result)

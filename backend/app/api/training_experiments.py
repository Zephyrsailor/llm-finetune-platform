"""Training experiment metadata, comparison, and export API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_current_user,
    get_training_experiment_service,
)
from app.models import User
from app.schemas.training_experiments import (
    TrainingExperimentCompareRequest,
    TrainingExperimentCompareResponse,
    TrainingExperimentDetail,
    TrainingExperimentExportRequest,
    TrainingExperimentExportResponse,
    TrainingExperimentSummary,
)
from app.services.errors import (
    TrainingExperimentError,
    TrainingJobError,
    WorkspaceNotFoundError,
)
from app.services.training_experiments import TrainingExperimentService

router = APIRouter(prefix="/v1/training/experiments", tags=["training"])


@router.get(
    "",
    response_model=list[TrainingExperimentSummary],
)
async def list_training_experiments(
    workspace_id: int = Query(..., description="工作空间 ID"),
    job_id: int | None = Query(None, description="筛选指定训练任务"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    current_user: User = Depends(get_current_user),
    service: TrainingExperimentService = Depends(get_training_experiment_service),
) -> list[TrainingExperimentSummary]:
    try:
        runs = service.list_runs(
            workspace_id=workspace_id,
            current_user=current_user,
            job_id=job_id,
            limit=limit,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingExperimentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [TrainingExperimentSummary.model_validate(run) for run in runs]


@router.get(
    "/{run_id}",
    response_model=TrainingExperimentDetail,
)
async def get_training_experiment_detail(
    run_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingExperimentService = Depends(get_training_experiment_service),
) -> TrainingExperimentDetail:
    try:
        detail = service.get_run_detail(run_id, current_user=current_user)
    except (TrainingExperimentError, TrainingJobError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:  # defensive branch
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TrainingExperimentDetail.model_validate(detail)


@router.post(
    "/compare",
    response_model=TrainingExperimentCompareResponse,
)
async def compare_training_experiments(
    payload: TrainingExperimentCompareRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingExperimentService = Depends(get_training_experiment_service),
) -> TrainingExperimentCompareResponse:
    try:
        result = service.compare_runs(
            payload.run_a_id,
            payload.run_b_id,
            current_user=current_user,
        )
    except (TrainingExperimentError, TrainingJobError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingExperimentCompareResponse.model_validate(result)


@router.post(
    "/export",
    response_model=TrainingExperimentExportResponse,
)
async def export_training_experiments(
    payload: TrainingExperimentExportRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingExperimentService = Depends(get_training_experiment_service),
) -> TrainingExperimentExportResponse:
    try:
        result = service.export_runs(
            payload.run_ids,
            workspace_id=payload.workspace_id,
            export_format=payload.format,
            current_user=current_user,
        )
    except (TrainingExperimentError, TrainingJobError, WorkspaceNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingExperimentExportResponse.model_validate(result)

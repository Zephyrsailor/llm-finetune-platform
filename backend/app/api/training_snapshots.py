"""Training snapshot API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_training_snapshot_service
from app.models import User
from app.schemas.training import TrainingRunResponse
from app.schemas.training_snapshots import (
    TrainingSnapshotResponse,
    TrainingSnapshotResumeRequest,
    TrainingSnapshotRollbackRequest,
)
from app.services.errors import TrainingSnapshotError
from app.services.training_snapshots import TrainingSnapshotService

router = APIRouter(prefix="/v1/training/snapshots", tags=["training"])


@router.get("", response_model=list[TrainingSnapshotResponse])
async def list_training_snapshots(
    workspace_id: int | None = Query(None, description="工作空间 ID"),
    run_id: int | None = Query(None, description="训练运行 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingSnapshotService = Depends(get_training_snapshot_service),
) -> list[TrainingSnapshotResponse]:
    try:
        snapshots = service.list_snapshots(
            workspace_id=workspace_id,
            run_id=run_id,
            current_user=current_user,
        )
    except TrainingSnapshotError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [TrainingSnapshotResponse.model_validate(snapshot) for snapshot in snapshots]


@router.get("/{snapshot_id}", response_model=TrainingSnapshotResponse)
async def get_training_snapshot(
    snapshot_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingSnapshotService = Depends(get_training_snapshot_service),
) -> TrainingSnapshotResponse:
    try:
        snapshot = service.get_snapshot(snapshot_id, current_user)
    except TrainingSnapshotError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TrainingSnapshotResponse.model_validate(snapshot)


@router.post(
    "/{snapshot_id}:resume",
    response_model=TrainingRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_training_from_snapshot(
    snapshot_id: int,
    payload: TrainingSnapshotResumeRequest | None = None,
    current_user: User = Depends(get_current_user),
    service: TrainingSnapshotService = Depends(get_training_snapshot_service),
) -> TrainingRunResponse:
    try:
        run = service.resume_from_snapshot(
            snapshot_id,
            current_user=current_user,
            notes=payload.notes if payload else None,
        )
    except TrainingSnapshotError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingRunResponse.model_validate(run)


@router.post(
    "/{snapshot_id}:rollback",
    response_model=TrainingSnapshotResponse,
    status_code=status.HTTP_200_OK,
)
async def rollback_training_snapshot(
    snapshot_id: int,
    payload: TrainingSnapshotRollbackRequest | None = None,
    current_user: User = Depends(get_current_user),
    service: TrainingSnapshotService = Depends(get_training_snapshot_service),
) -> TrainingSnapshotResponse:
    try:
        snapshot = service.rollback_snapshot(
            snapshot_id,
            current_user=current_user,
            reason=payload.reason if payload else None,
        )
    except TrainingSnapshotError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingSnapshotResponse.model_validate(snapshot)

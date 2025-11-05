"""Training template and job API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user, get_training_service
from app.models import User
from app.schemas.training import (
    TrainingJobCreateRequest,
    TrainingJobResponse,
    TrainingRunResponse,
    TrainingTemplateCloneRequest,
    TrainingTemplateCreateRequest,
    TrainingTemplateResponse,
    TrainingTemplateUpdateRequest,
    TrainingWizardDraftRequest,
    TrainingWizardDraftResponse,
    TrainingWizardValidateRequest,
    TrainingWizardValidateResponse,
    TrainingFeedbackSummaryResponse,
)
from app.services.training import TrainingService
from app.services.errors import (
    DatasetNotFoundError,
    DatasetVersionError,
    TrainingJobError,
    TrainingTemplateError,
    TrainingValidationError,
    WorkspaceNotFoundError,
    AccessDeniedError,
)

router = APIRouter(prefix="/v1/training", tags=["training"])


@router.get(
    "/templates",
    response_model=list[TrainingTemplateResponse],
)
async def list_training_templates(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> list[TrainingTemplateResponse]:
    try:
        templates = service.list_templates(workspace_id=workspace_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [TrainingTemplateResponse.model_validate(template) for template in templates]


@router.post(
    "/templates",
    response_model=TrainingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_training_template(
    payload: TrainingTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingTemplateResponse:
    try:
        template = service.create_template(
            workspace_id=payload.workspace_id,
            name=payload.name,
            base_model=payload.base_model,
            adapter_type=payload.adapter_type,
            params=payload.params,
            description=payload.description,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except TrainingTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingTemplateResponse.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    response_model=TrainingTemplateResponse,
)
async def update_training_template(
    template_id: int,
    payload: TrainingTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingTemplateResponse:
    try:
        template = service.update_template(
            template_id=template_id,
            name=payload.name,
            description=payload.description,
            base_model=payload.base_model,
            adapter_type=payload.adapter_type,
            params=payload.params,
            current_user=current_user,
        )
    except TrainingTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return TrainingTemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}:clone",
    response_model=TrainingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_training_template(
    template_id: int,
    payload: TrainingTemplateCloneRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingTemplateResponse:
    try:
        template = service.clone_template(
            template_id=template_id,
            name=payload.name,
            current_user=current_user,
        )
    except TrainingTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TrainingTemplateResponse.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_training_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> Response:
    try:
        service.delete_template(template_id=template_id, current_user=current_user)
    except TrainingTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/wizard/draft",
    response_model=TrainingWizardDraftResponse,
    status_code=status.HTTP_200_OK,
)
async def save_training_wizard_draft(
    payload: TrainingWizardDraftRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingWizardDraftResponse:
    try:
        result = service.save_wizard_draft(
            workspace_id=payload.workspace_id,
            payload=payload.payload,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TrainingWizardDraftResponse.model_validate(result)


@router.get(
    "/wizard/draft",
    response_model=TrainingWizardDraftResponse,
)
async def get_training_wizard_draft(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingWizardDraftResponse:
    try:
        draft = service.get_wizard_draft(
            workspace_id=workspace_id,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if draft is None:
        draft = {"workspace_id": workspace_id, "payload": None, "updated_at": None}
    return TrainingWizardDraftResponse.model_validate(draft)


@router.post(
    "/wizard/validate",
    response_model=TrainingWizardValidateResponse,
    status_code=status.HTTP_200_OK,
)
async def validate_training_wizard(
    payload: TrainingWizardValidateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingWizardValidateResponse:
    try:
        result = service.validate_wizard_configuration(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            dataset_version_id=payload.dataset_version_id,
            dataset_format_version_id=payload.dataset_format_version_id,
            template_id=payload.training_template_id,
            base_model=payload.base_model,
            adapter_type=payload.adapter_type,
            params=payload.params,
            requested_gpus=payload.requested_gpus,
            queue_name=payload.queue_name,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DatasetNotFoundError, DatasetVersionError, TrainingJobError, TrainingTemplateError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return TrainingWizardValidateResponse.model_validate(result)


@router.post(
    "/jobs",
    response_model=TrainingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_training_job(
    payload: TrainingJobCreateRequest,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingJobResponse:
    try:
        job = service.create_job(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            dataset_version_id=payload.dataset_version_id,
            dataset_format_version_id=payload.dataset_format_version_id,
            template_id=payload.training_template_id,
            base_model=payload.base_model,
            adapter_type=payload.adapter_type,
            params=payload.params,
            requested_gpus=payload.requested_gpus,
            queue_name=payload.queue_name,
            notes=payload.notes,
            current_user=current_user,
            ip_address=None,
            user_agent=None,
        )
        job, latest_run = service.get_job_with_latest_run(job.id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DatasetNotFoundError, DatasetVersionError, TrainingJobError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    response = TrainingJobResponse.model_validate(job)
    response.latest_run = TrainingRunResponse.model_validate(latest_run) if latest_run else None
    return response


@router.get(
    "/jobs/{job_id}",
    response_model=TrainingJobResponse,
)
async def get_training_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingJobResponse:
    try:
        job, latest_run = service.get_job_with_latest_run(job_id, current_user=current_user)
    except TrainingJobError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    response = TrainingJobResponse.model_validate(job)
    response.latest_run = TrainingRunResponse.model_validate(latest_run) if latest_run else None
    return response


@router.get(
    "/feedback-summaries",
    response_model=TrainingFeedbackSummaryResponse,
)
async def list_training_feedback_summaries(
    workspace_id: int = Query(..., description="工作空间 ID"),
    project_id: str | None = Query(None, description="项目 ID，可选"),
    limit: int = Query(20, description="返回条数", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> TrainingFeedbackSummaryResponse:
    project_id_value: int | None
    if project_id is None or project_id == "":
        project_id_value = None
    else:
        try:
            project_id_value = int(project_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="project_id 必须为整数",
            ) from exc

    try:
        payload = service.list_feedback_summaries(
            workspace_id=workspace_id,
            project_id=project_id_value,
            limit=limit,
            current_user=current_user,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return TrainingFeedbackSummaryResponse.model_validate(payload)

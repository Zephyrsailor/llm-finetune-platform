"""Knowledge base API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_user, get_knowledge_service
from app.models import KnowledgeEntryType, User
from app.schemas.knowledge import (
    KnowledgeEntryCreateRequest,
    KnowledgeEntryDetailResponse,
    KnowledgeEntryResponse,
    KnowledgeEntryVersionCreateRequest,
    KnowledgeEntryVersionResponse,
    KnowledgeTemplateCloneRequest,
)
from app.services.errors import AccessDeniedError, TrainingValidationError
from app.services.knowledge import KnowledgeBaseService

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


@router.get("/entries", response_model=list[KnowledgeEntryResponse])
async def list_knowledge_entries(
    workspace_id: int = Query(..., description="工作空间 ID"),
    project_id: int | None = Query(default=None, description="项目 ID，缺省显示通用模板"),
    entry_type: KnowledgeEntryType | None = Query(default=None, description="条目类型"),
    tag: str | None = Query(default=None, description="标签过滤"),
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
) -> list[KnowledgeEntryResponse]:
    try:
        entries = service.list_entries(
            workspace_id=workspace_id,
            project_id=project_id,
            entry_type=entry_type,
            tag=tag,
            current_user=current_user,
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [KnowledgeEntryResponse.model_validate(entry) for entry in entries]


@router.get("/entries/{entry_id}", response_model=KnowledgeEntryDetailResponse)
async def get_knowledge_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
) -> KnowledgeEntryDetailResponse:
    try:
        detail = service.get_entry(entry_id, current_user=current_user)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return KnowledgeEntryDetailResponse(
        entry=KnowledgeEntryResponse.model_validate(detail.entry),
        versions=[KnowledgeEntryVersionResponse.model_validate(item) for item in detail.versions],
    )


@router.post("/entries", response_model=KnowledgeEntryDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_entry(
    payload: KnowledgeEntryCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
) -> KnowledgeEntryDetailResponse:
    try:
        detail = service.create_entry(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            entry_type=payload.entry_type,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            content=payload.content,
            config_snapshot=payload.config_snapshot,
            summary=payload.summary,
            current_user=current_user,
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    request.state.response_status_code = status.HTTP_201_CREATED  # type: ignore[attr-defined]
    return KnowledgeEntryDetailResponse(
        entry=KnowledgeEntryResponse.model_validate(detail.entry),
        versions=[KnowledgeEntryVersionResponse.model_validate(item) for item in detail.versions],
    )


@router.post("/entries/{entry_id}/versions", response_model=KnowledgeEntryDetailResponse)
async def create_knowledge_entry_version(
    entry_id: int,
    payload: KnowledgeEntryVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
) -> KnowledgeEntryDetailResponse:
    try:
        detail = service.create_version(
            entry_id=entry_id,
            summary=payload.summary,
            content=payload.content,
            config_snapshot=payload.config_snapshot,
            current_user=current_user,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return KnowledgeEntryDetailResponse(
        entry=KnowledgeEntryResponse.model_validate(detail.entry),
        versions=[KnowledgeEntryVersionResponse.model_validate(item) for item in detail.versions],
    )


@router.post("/entries/{entry_id}/clone", response_model=KnowledgeEntryDetailResponse)
async def clone_knowledge_template(
    entry_id: int,
    payload: KnowledgeTemplateCloneRequest,
    current_user: User = Depends(get_current_user),
    service: KnowledgeBaseService = Depends(get_knowledge_service),
) -> KnowledgeEntryDetailResponse:
    try:
        detail = service.clone_template(
            entry_id=entry_id,
            target_project_id=payload.target_project_id,
            title=payload.title,
            current_user=current_user,
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return KnowledgeEntryDetailResponse(
        entry=KnowledgeEntryResponse.model_validate(detail.entry),
        versions=[KnowledgeEntryVersionResponse.model_validate(item) for item in detail.versions],
    )

"""Governance API endpoints for kanban workflow management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_governance_service,
    get_governance_comment_service,
    get_governance_approval_service,
)
from app.models import User, CommentEntityType, ApprovalTaskStatus
from app.schemas.governance import (
    KanbanBoardResponse,
    KanbanCardCreateRequest,
    KanbanCardResponse,
    KanbanCardUpdateRequest,
    KanbanReorderRequest,
    CommentCreateRequest,
    CommentResponse,
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
)
from app.services.errors import AccessDeniedError
from app.services.governance import (
    GovernanceApprovalService,
    GovernanceCommentService,
    GovernanceKanbanService,
)

router = APIRouter(prefix="/v1/governance", tags=["governance"])


def _extract_card_payload(board_payload: dict, card_id: int) -> dict | None:
    for column in board_payload.get("columns", []):
        for task in column.get("tasks", []):
            if task.get("id") == card_id:
                return task
    return None


@router.get(
    "/kanban/board",
    response_model=KanbanBoardResponse,
)
async def get_kanban_board(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: GovernanceKanbanService = Depends(get_governance_service),
) -> KanbanBoardResponse:
    payload = service.get_board(workspace_id=workspace_id, current_user=current_user)
    return KanbanBoardResponse.model_validate(payload)


@router.post(
    "/kanban/cards",
    response_model=KanbanCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_card(
    payload: KanbanCardCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceKanbanService = Depends(get_governance_service),
) -> KanbanCardResponse:
    card = service.create_manual_card(
        workspace_id=payload.workspace_id,
        project_id=payload.project_id,
        stage=payload.stage,
        status=payload.status,
        title=payload.title,
        description=payload.description,
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    board_payload = service.get_board(workspace_id=card.workspace_id, current_user=current_user)
    card_payload = _extract_card_payload(board_payload, card.id)
    if card_payload is None:
        card_payload = {
            "id": card.id,
            "stage": card.stage,
            "status": card.status,
            "title": card.title,
            "description": card.description,
            "order_index": card.order_index,
            "due_at": card.due_at,
            "reminder_minutes_before": card.reminder_minutes_before,
            "assignee": None,
            "linked_entity": None,
            "updated_at": card.updated_at,
        }
    return KanbanCardResponse.model_validate(card_payload)


@router.patch(
    "/kanban/cards/{card_id}",
    response_model=KanbanCardResponse,
)
async def update_card(
    card_id: int,
    payload: KanbanCardUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceKanbanService = Depends(get_governance_service),
) -> KanbanCardResponse:
    card = service.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="看板任务不存在")
    service.update_card(
        card=card,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        due_at=payload.due_at,
        reminder_minutes_before=payload.reminder_minutes_before,
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    board_payload = service.get_board(workspace_id=card.workspace_id, current_user=current_user)
    card_payload = _extract_card_payload(board_payload, card.id)
    if card_payload is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法加载更新后的任务")
    return KanbanCardResponse.model_validate(card_payload)


@router.post(
    "/kanban/cards/reorder",
    response_model=KanbanBoardResponse,
)
async def reorder_cards(
    payload: KanbanReorderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceKanbanService = Depends(get_governance_service),
) -> KanbanBoardResponse:
    service.reorder_cards(
        workspace_id=payload.workspace_id,
        moves=[move.model_dump() for move in payload.moves],
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    board_payload = service.get_board(workspace_id=payload.workspace_id, current_user=current_user)
    return KanbanBoardResponse.model_validate(board_payload)


@router.get(
    "/comments",
    response_model=list[CommentResponse],
)
async def list_comments(
    workspace_id: int = Query(..., description="工作空间 ID"),
    entity_type: CommentEntityType = Query(..., description="实体类型"),
    entity_id: int = Query(..., description="实体 ID"),
    current_user: User = Depends(get_current_user),
    service: GovernanceCommentService = Depends(get_governance_comment_service),
) -> list[CommentResponse]:
    try:
        payload = service.list_comments(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            current_user=current_user,
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [CommentResponse.model_validate(item) for item in payload]


@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    payload: CommentCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceCommentService = Depends(get_governance_comment_service),
) -> CommentResponse:
    try:
        result = service.create_comment(
            workspace_id=payload.workspace_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            body=payload.body,
            mentions=payload.mentions,
            attachments=[attachment.model_dump() for attachment in payload.attachments],
            context=payload.context,
            current_user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CommentResponse.model_validate(result)


@router.get(
    "/approvals",
    response_model=list[ApprovalRequestResponse],
)
async def list_approvals(
    workspace_id: int = Query(..., description="工作空间 ID"),
    entity_type: CommentEntityType = Query(..., description="实体类型"),
    entity_id: int = Query(..., description="实体 ID"),
    current_user: User = Depends(get_current_user),
    service: GovernanceApprovalService = Depends(get_governance_approval_service),
) -> list[ApprovalRequestResponse]:
    try:
        payload = service.list_requests(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            current_user=current_user,
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ApprovalRequestResponse.model_validate(item) for item in payload]


@router.post(
    "/approvals",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_request(
    payload: ApprovalCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceApprovalService = Depends(get_governance_approval_service),
) -> ApprovalRequestResponse:
    try:
        result = service.create_request(
            workspace_id=payload.workspace_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            title=payload.title,
            description=payload.description,
            approver_ids=payload.approver_ids,
            due_at=payload.due_at,
            current_user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApprovalRequestResponse.model_validate(result)


@router.post(
    "/approvals/{request_id}/decisions",
    response_model=ApprovalRequestResponse,
)
async def record_approval_decision(
    request_id: int,
    payload: ApprovalDecisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: GovernanceApprovalService = Depends(get_governance_approval_service),
) -> ApprovalRequestResponse:
    if payload.status == ApprovalTaskStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="审批状态无效")
    try:
        result = service.record_decision(
            request_id=request_id,
            decision_status=payload.status,
            notes=payload.notes,
            current_user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApprovalRequestResponse.model_validate(result)

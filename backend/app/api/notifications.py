"""Notification center API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user, get_notification_service
from app.models import User
from app.schemas.notification import (
    NotificationChannelCreateRequest,
    NotificationChannelResponse,
    NotificationChannelUpdateRequest,
    NotificationEventResponse,
)
from app.services.errors import AccessDeniedError
from app.services.notification import NotificationService

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get(
    "/channels",
    response_model=list[NotificationChannelResponse],
)
async def list_notification_channels(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> list[NotificationChannelResponse]:
    try:
        channels = service.list_channels(workspace_id, current_user=current_user)
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [NotificationChannelResponse.model_validate(channel) for channel in channels]


@router.post(
    "/channels",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_channel(
    payload: NotificationChannelCreateRequest,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationChannelResponse:
    try:
        channel = service.create_channel(
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            name=payload.name,
            channel_type=payload.channel_type,
            event_types=payload.event_types,
            config=payload.config,
            is_active=payload.is_active,
            current_user=current_user,
        )
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return NotificationChannelResponse.model_validate(channel)


@router.delete(
    "/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_notification_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> Response:
    try:
        service.delete_channel(channel_id=channel_id, current_user=current_user)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在") from None
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/events",
    response_model=list[NotificationEventResponse],
)
async def list_notification_events(
    workspace_id: int = Query(..., description="工作空间 ID"),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> list[NotificationEventResponse]:
    try:
        events = service.list_events(workspace_id=workspace_id, current_user=current_user)
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [NotificationEventResponse.model_validate(event) for event in events]


@router.post(
    "/events/{event_id}/retry",
    response_model=NotificationEventResponse,
)
async def retry_notification_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationEventResponse:
    try:
        record = service.retry_event(record_id=event_id, current_user=current_user)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知记录不存在") from None
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return NotificationEventResponse.model_validate(record)


@router.patch(
    "/channels/{channel_id}",
    response_model=NotificationChannelResponse,
)
async def update_notification_channel(
    channel_id: int,
    payload: NotificationChannelUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationChannelResponse:
    update_data = payload.model_dump(exclude_unset=True)
    project_value = service._UNSET
    if "project_id" in update_data:
        project_value = update_data["project_id"]
    try:
        channel = service.update_channel(
            channel_id=channel_id,
            name=update_data.get("name"),
            event_types=update_data.get("event_types"),
            config=update_data.get("config"),
            is_active=update_data.get("is_active"),
            project_id=project_value,
            current_user=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在") from None
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return NotificationChannelResponse.model_validate(channel)

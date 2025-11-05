"""Inference API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_inference_actor, get_inference_service, get_current_user
from app.schemas.inference import (
    GeneratedOutput,
    InferenceInvokeRequest,
    InferenceInvokeResponse,
    InferenceLogListResponse,
    InferenceLogResponse,
    InferenceApiKeyCreateRequest,
    InferenceApiKeyCreationResponse,
    InferenceApiKeyListResponse,
    InferenceApiKeyResponse,
)
from app.services.errors import AccessDeniedError, ModelRegistryError, RateLimitExceeded, WorkspaceNotFoundError
from app.services.inference import InferenceService, InferenceActor

router = APIRouter(prefix="/v1/inference", tags=["inference"])


@router.post(
    "",
    response_model=InferenceInvokeResponse,
)
async def invoke_inference(
    payload: InferenceInvokeRequest,
    actor: InferenceActor = Depends(get_inference_actor),
    service: InferenceService = Depends(get_inference_service),
) -> InferenceInvokeResponse:
    try:
        result = service.invoke_inference(
            workspace_id=payload.workspace_id,
            deployment_id=payload.deployment_id,
            model_version_id=payload.model_version_id,
            inputs=payload.inputs,
            parameters=payload.parameters,
            actor=actor,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (AccessDeniedError, ModelRegistryError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    outputs = [GeneratedOutput(**item) for item in result["outputs"]]
    return InferenceInvokeResponse(
        call_id=result["call_id"],
        deployment_id=result["deployment_id"],
        model_version_id=result["model_version_id"],
        outputs=outputs,
        latency_ms=result["latency_ms"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
    )


@router.get(
    "/logs",
    response_model=InferenceLogListResponse,
)
async def list_inference_logs(
    workspace_id: int = Query(..., description="工作空间 ID"),
    limit: int = Query(50, ge=1, le=200),
    service: InferenceService = Depends(get_inference_service),
    current_user=Depends(get_current_user),
) -> InferenceLogListResponse:
    try:
        logs = service.list_logs(workspace_id=workspace_id, current_user=current_user, limit=limit)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return InferenceLogListResponse(logs=logs)


@router.get(
    "/calls/{call_id}",
    response_model=InferenceLogResponse,
)
async def get_inference_call(
    call_id: int,
    workspace_id: int = Query(...),
    service: InferenceService = Depends(get_inference_service),
    current_user=Depends(get_current_user),
) -> InferenceLogResponse:
    try:
        call = service.get_call(workspace_id=workspace_id, call_id=call_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ModelRegistryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return InferenceLogResponse.model_validate(call)


@router.post(
    "/api-keys",
    response_model=InferenceApiKeyCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: InferenceApiKeyCreateRequest,
    request: Request,
    service: InferenceService = Depends(get_inference_service),
    current_user=Depends(get_current_user),
) -> InferenceApiKeyCreationResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    try:
        api_key, secret = service.create_api_key(
            workspace_id=payload.workspace_id,
            name=payload.name,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            daily_quota=payload.daily_quota,
            current_user=current_user,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return InferenceApiKeyCreationResponse(
        api_key=InferenceApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            is_active=api_key.is_active,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            daily_quota=api_key.daily_quota,
            created_at=api_key.created_at,
            revoked_at=api_key.revoked_at,
            last_used_at=api_key.last_used_at,
        ),
        secret=secret,
    )


@router.get(
    "/api-keys",
    response_model=InferenceApiKeyListResponse,
)
async def list_api_keys(
    workspace_id: int = Query(...),
    service: InferenceService = Depends(get_inference_service),
    current_user=Depends(get_current_user),
) -> InferenceApiKeyListResponse:
    try:
        api_keys = service.list_api_keys(workspace_id=workspace_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return InferenceApiKeyListResponse(
        items=[
            InferenceApiKeyResponse(
                id=item.id,
                name=item.name,
                is_active=item.is_active,
                rate_limit_per_minute=item.rate_limit_per_minute,
                daily_quota=item.daily_quota,
                created_at=item.created_at,
                revoked_at=item.revoked_at,
                last_used_at=item.last_used_at,
            )
            for item in api_keys
        ]
    )


@router.delete(
    "/api-keys/{api_key_id}",
    response_model=InferenceApiKeyResponse,
)
async def revoke_api_key(
    api_key_id: int,
    request: Request,
    workspace_id: int = Query(...),
    service: InferenceService = Depends(get_inference_service),
    current_user=Depends(get_current_user),
) -> InferenceApiKeyResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    try:
        api_key = service.revoke_api_key(
            workspace_id=workspace_id,
            api_key_id=api_key_id,
            current_user=current_user,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return InferenceApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        is_active=api_key.is_active,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        daily_quota=api_key.daily_quota,
        created_at=api_key.created_at,
        revoked_at=api_key.revoked_at,
        last_used_at=api_key.last_used_at,
    )

"""Workspace management API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_user, get_role_service, get_workspace_service
from app.models import User, Workspace
from app.schemas.role import (
    RoleAssignmentRequest,
    RoleAssignmentSummary,
    RoleCreateRequest,
    RoleMatrixResponse,
    RoleSummary,
    RoleUpdateRequest,
)
from app.schemas.workspace import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectInfo,
    WorkspaceCreateRequest,
    WorkspaceDetail,
    WorkspaceMemberInfo,
    WorkspaceUpdateRequest,
)
from app.services.errors import (
    AccessDeniedError,
    ProjectConflictError,
    RoleConflictError,
    RoleNotFoundError,
    WorkspaceConflictError,
    WorkspaceNotFoundError,
)
from app.services.role_management import RoleManagementService
from app.services.workspaces import WorkspaceService, WorkspaceSnapshot

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def _snapshot_to_detail(snapshot: WorkspaceSnapshot) -> WorkspaceDetail:
    workspace: Workspace = snapshot.workspace
    members = [
        WorkspaceMemberInfo(user_id=user.id, email=user.email, role=member.role)
        for member, user in snapshot.members
    ]
    projects = [ProjectInfo.model_validate(project) for project in snapshot.projects]
    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        plan=workspace.plan,
        status=workspace.status,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        members=members,
        projects=projects,
    )


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return ip_address, user_agent


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    ip_address, user_agent = _client_meta(request)
    try:
        snapshot = service.create_workspace(
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            plan=payload.plan,
            member_ids=payload.member_ids,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _snapshot_to_detail(snapshot)


@router.get("", response_model=list[WorkspaceDetail])
def list_workspaces(
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceDetail]:
    snapshots = service.list_workspaces(current_user=current_user)
    return [_snapshot_to_detail(snapshot) for snapshot in snapshots]


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    try:
        snapshot = service.get_workspace(workspace_id=workspace_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return _snapshot_to_detail(snapshot)


@router.patch("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    ip_address, user_agent = _client_meta(request)
    try:
        snapshot = service.update_workspace(
            workspace_id=workspace_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            plan=payload.plan,
            status=payload.status,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _snapshot_to_detail(snapshot)


@router.post("/{workspace_id}/projects", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    workspace_id: int,
    payload: ProjectCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> ProjectCreateResponse:
    ip_address, user_agent = _client_meta(request)
    try:
        snapshot, created_paths = service.create_project(
            workspace_id=workspace_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ProjectCreateResponse(workspace=_snapshot_to_detail(snapshot), created_paths=created_paths)


@router.get("/{workspace_id}/roles", response_model=RoleMatrixResponse)
def get_role_matrix(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleManagementService = Depends(get_role_service),
) -> RoleMatrixResponse:
    try:
        matrix = service.get_matrix(workspace_id=workspace_id, current_user=current_user)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return RoleMatrixResponse.model_validate(matrix)


@router.post("/{workspace_id}/roles", response_model=RoleSummary, status_code=status.HTTP_201_CREATED)
def create_role(
    workspace_id: int,
    payload: RoleCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RoleManagementService = Depends(get_role_service),
) -> RoleSummary:
    ip_address, user_agent = _client_meta(request)
    try:
        role = service.create_role(
            workspace_id=workspace_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            operations=payload.operations,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RoleSummary.model_validate(role)


@router.patch("/{workspace_id}/roles/{role_id}", response_model=RoleSummary)
def update_role(
    workspace_id: int,
    role_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RoleManagementService = Depends(get_role_service),
) -> RoleSummary:
    ip_address, user_agent = _client_meta(request)
    try:
        role = service.update_role(
            workspace_id=workspace_id,
            role_id=role_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            operations=payload.operations,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RoleSummary.model_validate(role)


@router.post("/{workspace_id}/members/{user_id}/roles", response_model=RoleAssignmentSummary)
def set_member_roles(
    workspace_id: int,
    user_id: int,
    payload: RoleAssignmentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: RoleManagementService = Depends(get_role_service),
) -> RoleAssignmentSummary:
    ip_address, user_agent = _client_meta(request)
    try:
        assignment = service.set_member_roles(
            workspace_id=workspace_id,
            target_user_id=user_id,
            role_ids=payload.role_ids,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RoleAssignmentSummary.model_validate(assignment)

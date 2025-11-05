"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_user, get_dashboard_service
from app.models import User
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import DashboardService
from app.services.errors import AccessDeniedError, WorkspaceNotFoundError

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    request: Request,
    workspace_id: int | None = Query(default=None, ge=1, description="可选的工作空间过滤条件"),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummary:
    """Return aggregated dashboard summary for accessible workspaces."""
    try:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        return service.get_summary(
            current_user=current_user,
            workspace_id=workspace_id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

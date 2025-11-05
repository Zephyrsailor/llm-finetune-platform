"""Reusable API dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from app.core import security
from app.core.database import get_session
from app.models import User
from app.repositories.user import UserRepository
from app.services.dashboard import DashboardService
from app.services.data_hub import DataHubService
from app.services.role_management import RoleManagementService
from app.services.workspaces import WorkspaceService
from app.services.training import TrainingService
from app.services.training_monitoring import TrainingMonitoringService
from app.services.training_snapshots import TrainingSnapshotService
from app.services.evaluation import EvaluationService
from app.services.training_experiments import TrainingExperimentService
from app.services.model_registry import ModelRegistryService
from app.services.deployment import DeploymentService
from app.services.inference import InferenceService, InferenceActor
from app.services.runtime_monitoring import RuntimeMonitoringService
from app.services.knowledge import KnowledgeBaseService
from app.services.notification import NotificationService
from app.services.governance import (
    GovernanceKanbanService,
    GovernanceCommentService,
    GovernanceApprovalService,
)


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Resolve the authenticated user from the Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or " " not in auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少凭证")
    scheme, token = auth_header.split(" ", 1)
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="凭证格式不正确")
    try:
        payload = security.decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="凭证无效") from exc
    user_id = int(payload["sub"])
    user = UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已失效")
    return user


def get_workspace_service(session: Session = Depends(get_session)) -> WorkspaceService:
    """Provide a WorkspaceService instance for request scope."""
    return WorkspaceService(session)


def get_role_service(session: Session = Depends(get_session)) -> RoleManagementService:
    """Provide role management service for request scope."""
    return RoleManagementService(session)


def get_data_hub_service(session: Session = Depends(get_session)) -> DataHubService:
    """Provide DataHub service for request scope."""
    return DataHubService(session)


def get_dashboard_service(session: Session = Depends(get_session)) -> DashboardService:
    """Provide Dashboard service for request scope."""
    return DashboardService(session)


def get_training_service(session: Session = Depends(get_session)) -> TrainingService:
    """Provide Training service for request scope."""
    return TrainingService(session)


def get_training_monitoring_service(session: Session = Depends(get_session)) -> TrainingMonitoringService:
    """Provide Training monitoring service for request scope."""
    return TrainingMonitoringService(session)


def get_training_snapshot_service(session: Session = Depends(get_session)) -> TrainingSnapshotService:
    """Provide Training snapshot service for request scope."""
    return TrainingSnapshotService(session)


def get_training_experiment_service(session: Session = Depends(get_session)) -> TrainingExperimentService:
    """Provide Training experiment service for request scope."""
    return TrainingExperimentService(session)


def get_evaluation_service(session: Session = Depends(get_session)) -> EvaluationService:
    """Provide Evaluation service for request scope."""
    return EvaluationService(session)


def get_model_registry_service(session: Session = Depends(get_session)) -> ModelRegistryService:
    """Provide Model Registry service for request scope."""
    return ModelRegistryService(session)


def get_deployment_service(session: Session = Depends(get_session)) -> DeploymentService:
    """Provide Deployment service for request scope."""
    return DeploymentService(session)


def get_inference_service(session: Session = Depends(get_session)) -> InferenceService:
    """Provide Inference service for request scope."""
    return InferenceService(session)


def get_runtime_monitoring_service(session: Session = Depends(get_session)) -> RuntimeMonitoringService:
    """Provide runtime monitoring service for request scope."""
    return RuntimeMonitoringService(session)


def get_notification_service(session: Session = Depends(get_session)) -> NotificationService:
    """Provide notification service for request scope."""
    return NotificationService(session)


def get_knowledge_service(session: Session = Depends(get_session)) -> KnowledgeBaseService:
    """Provide knowledge base service for request scope."""
    return KnowledgeBaseService(session)


def get_governance_service(
    session: Session = Depends(get_session),
    notification_service: NotificationService = Depends(get_notification_service),
) -> GovernanceKanbanService:
    """Provide governance service for request scope."""
    return GovernanceKanbanService(session, notification_service=notification_service)


def get_governance_comment_service(
    session: Session = Depends(get_session),
    notification_service: NotificationService = Depends(get_notification_service),
) -> GovernanceCommentService:
    """Provide governance comment service for request scope."""
    return GovernanceCommentService(session, notification_service=notification_service)


def get_governance_approval_service(
    session: Session = Depends(get_session),
    notification_service: NotificationService = Depends(get_notification_service),
) -> GovernanceApprovalService:
    """Provide governance approval service for request scope."""
    return GovernanceApprovalService(session, notification_service=notification_service)

def get_inference_actor(
    request: Request,
    session: Session = Depends(get_session),
    inference_service: InferenceService = Depends(get_inference_service),
) -> InferenceActor:
    """Resolve request identity for inference endpoints (user or API key)."""
    api_key_header = request.headers.get("X-LLMFT-API-Key")
    if api_key_header:
        api_key = inference_service.authenticate_api_key(api_key_header.strip())
        if api_key is None or not api_key.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效或已停用")
        return InferenceActor(user=None, api_key_id=api_key.id)

    user = get_current_user(request, session)
    return InferenceActor(user=user, api_key_id=None)

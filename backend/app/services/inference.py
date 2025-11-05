"""Service layer for inference API orchestration."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Iterable

from sqlmodel import Session

from app.core.config import settings
from app.core.security import hash_api_key, generate_api_key, verify_api_key
from app.models import (
    Deployment,
    DeploymentStatus,
    InferenceApiKey,
    InferenceCallStatus,
    InferenceUsage,
    ModelVersion,
    UsageWindowScope,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.deployment import DeploymentRepository
from app.repositories.inference import (
    InferenceApiKeyRepository,
    InferenceCallRepository,
    InferenceUsageRepository,
)
from app.repositories.model_registry import ModelVersionRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import AccessDeniedError, RateLimitExceeded, WorkspaceNotFoundError, ModelRegistryError
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation
from app.models import User


@dataclass(slots=True)
class InferenceActor:
    """Identity of the caller invoking inference."""

    user: User | None
    api_key_id: int | None


class InferenceService:
    """Co-ordinate inference invocations, rate limiting and logging."""

    def __init__(self, session: Session):
        self._session = session
        self._deployments = DeploymentRepository(session)
        self._model_versions = ModelVersionRepository(session)
        self._calls = InferenceCallRepository(session)
        self._api_keys = InferenceApiKeyRepository(session)
        self._usage = InferenceUsageRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)

    @contextmanager
    def _transaction(self):
        if self._session.in_transaction():
            with self._session.begin_nested():
                yield
        else:
            with self._session.begin():
                yield

    # ------------------------------------------------------------------ #
    # API keys
    # ------------------------------------------------------------------ #

    def create_api_key(
        self,
        *,
        workspace_id: int,
        name: str,
        rate_limit_per_minute: int | None,
        daily_quota: int | None,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[InferenceApiKey, str]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user)
        raw_key = generate_api_key()
        key_prefix = raw_key[:16]
        hashed = hash_api_key(raw_key)
        with self._transaction():
            api_key = self._api_keys.create(
                workspace_id=workspace.id,
                name=name,
                key_prefix=key_prefix,
                key_hash=hashed,
                rate_limit_per_minute=rate_limit_per_minute,
                daily_quota=daily_quota,
                created_by=current_user.id,
            )
        self._audits.record(
            event_type="inference.api_key.created",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": workspace.id,
                "api_key_id": api_key.id,
                "name": name,
            },
        )
        return api_key, raw_key

    def list_api_keys(self, *, workspace_id: int, current_user: User) -> list[InferenceApiKey]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user)
        return list(self._api_keys.list_for_workspace(workspace.id))

    def revoke_api_key(
        self,
        *,
        workspace_id: int,
        api_key_id: int,
        current_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> InferenceApiKey:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user)
        key = self._session.get(InferenceApiKey, api_key_id)
        if key is None or key.workspace_id != workspace.id:
            raise AccessDeniedError("API 密钥不存在或不属于该工作空间。")
        with self._transaction():
            self._api_keys.revoke(key)
        self._audits.record(
            event_type="inference.api_key.revoked",
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": workspace.id, "api_key_id": key.id},
        )
        return key

    # ------------------------------------------------------------------ #
    # Inference flow
    # ------------------------------------------------------------------ #

    def invoke_inference(
        self,
        *,
        workspace_id: int,
        deployment_id: int | None,
        model_version_id: int | None,
        inputs: list[str],
        parameters: dict[str, Any] | None,
        actor: InferenceActor,
    ) -> dict[str, Any]:
        workspace = self._ensure_workspace(workspace_id)
        user_id = actor.user.id if actor.user else None
        api_key_entity: InferenceApiKey | None = None
        if actor.api_key_id is not None:
            api_key_entity = self._api_keys.get(actor.api_key_id)
            if api_key_entity is None or not api_key_entity.is_active:
                raise AccessDeniedError("API 密钥无效或已停用。")
            if api_key_entity.workspace_id != workspace.id:
                raise AccessDeniedError("API 密钥无权访问该工作空间。")
        else:
            self._require_use(workspace.id, actor.user)

        deployment = self._resolve_deployment(workspace.id, deployment_id, model_version_id)
        model_version = self._resolve_model_version(model_version_id or deployment.model_version_id)
        project_id = deployment.project_id
        api_key_id = api_key_entity.id if api_key_entity else None

        token_estimate = self._estimate_tokens(inputs)
        request_payload = {
            "inputs": inputs,
            "parameters": parameters or {},
        }

        result_payload: dict[str, Any] | None = None
        try:
            with self._transaction():
                self._enforce_limits(
                    workspace_id=workspace.id,
                    api_key=api_key_entity,
                    token_estimate=token_estimate,
                )
                start = perf_counter()
                outputs = self._generate_stub_outputs(deployment, inputs, parameters)
                elapsed_ms = (perf_counter() - start) * 1000
                output_tokens = self._estimate_tokens([item["output"] for item in outputs])

                call = self._calls.create(
                    workspace_id=workspace.id,
                    project_id=project_id,
                    deployment_id=deployment.id,
                    model_version_id=model_version.id,
                    api_key_id=api_key_id,
                    user_id=user_id,
                    request_payload=request_payload,
                    response_payload={"outputs": outputs},
                    status=InferenceCallStatus.SUCCESS,
                    latency_ms=elapsed_ms,
                    input_tokens=token_estimate,
                    output_tokens=output_tokens,
                    error_message=None,
                )
                if api_key_entity is not None:
                    self._api_keys.mark_used(api_key_entity)
                result_payload = {
                    "call_id": call.id,
                    "deployment_id": deployment.id,
                    "model_version_id": model_version.id,
                    "outputs": outputs,
                    "latency_ms": elapsed_ms,
                    "input_tokens": token_estimate,
                    "output_tokens": output_tokens,
                }
        except RateLimitExceeded as exc:
            self._session.rollback()
            self._record_rate_limit_event(
                workspace_id=workspace.id,
                project_id=project_id,
                deployment_id=deployment.id,
                model_version_id=model_version.id,
                api_key_id=api_key_id,
                user_id=user_id,
                request_payload=request_payload,
                token_estimate=token_estimate,
                message=str(exc),
            )
            raise

        if result_payload is None:
            raise RuntimeError("推理调用未生成结果。")
        return result_payload

    def list_logs(
        self,
        *,
        workspace_id: int,
        current_user: User,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user)
        calls = self._calls.list_for_workspace(workspace_id=workspace.id, limit=limit)
        return [
            {
                "id": call.id,
                "deployment_id": call.deployment_id,
                "model_version_id": call.model_version_id,
                "status": call.status.value,
                "latency_ms": call.latency_ms,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "created_at": call.created_at.isoformat(),
            }
            for call in calls
        ]

    def get_call(
        self,
        *,
        workspace_id: int,
        call_id: int,
        current_user: User,
    ) -> dict[str, Any]:
        workspace = self._ensure_workspace(workspace_id)
        self._require_manage(workspace.id, current_user)
        call = self._calls.get(call_id)
        if call is None or call.workspace_id != workspace.id:
            raise ModelRegistryError("推理调用记录不存在。")
        return {
            "id": call.id,
            "deployment_id": call.deployment_id,
            "model_version_id": call.model_version_id,
            "status": call.status.value,
            "latency_ms": call.latency_ms,
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "created_at": call.created_at.isoformat(),
            "error_message": call.error_message,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _ensure_workspace(self, workspace_id: int):
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("工作空间不存在。")
        return workspace

    def _require_manage(self, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.DEPLOYMENT_MANAGE,
            ip_address=None,
            user_agent=None,
        )

    def _require_use(self, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.INFERENCE_USE,
            ip_address=None,
            user_agent=None,
        )

    def _resolve_deployment(
        self,
        workspace_id: int,
        deployment_id: int | None,
        model_version_id: int | None,
    ) -> Deployment:
        deployment: Deployment | None = None
        if deployment_id is not None:
            deployment = self._deployments.get(deployment_id)
            if deployment is None or deployment.workspace_id != workspace_id:
                raise ModelRegistryError("部署记录不存在或不属于该工作空间。")
        elif model_version_id is not None:
            deployment = self._deployments.get_active_for_model_version(model_version_id)
            if deployment is None or deployment.workspace_id != workspace_id:
                raise ModelRegistryError("未找到对应模型的活动部署，无法执行推理。")
        else:
            raise ModelRegistryError("必须指定部署 ID 或模型版本 ID。")

        if deployment.status != DeploymentStatus.ACTIVE:
            raise ModelRegistryError("目标部署未处于可用状态。")
        return deployment

    def _resolve_model_version(self, model_version_id: int) -> ModelVersion:
        version = self._model_versions.get(model_version_id)
        if version is None:
            raise ModelRegistryError("模型版本不存在。")
        return version

    def _enforce_limits(
        self,
        *,
        workspace_id: int,
        api_key: InferenceApiKey | None,
        token_estimate: int,
    ) -> None:
        now = datetime.utcnow()
        minute_window = now.replace(second=0, microsecond=0)
        day_window = now.replace(hour=0, minute=0, second=0, microsecond=0)
        rate_limit = api_key.rate_limit_per_minute if api_key and api_key.rate_limit_per_minute else settings.inference_rate_limit_per_minute
        quota_limit = api_key.daily_quota if api_key and api_key.daily_quota else settings.inference_daily_quota

        minute_usage = self._usage.increment(
            workspace_id=workspace_id,
            scope=UsageWindowScope.MINUTE,
            window_start=minute_window,
            requests=1,
            tokens=token_estimate,
        )
        if minute_usage.request_count > rate_limit:
            raise RateLimitExceeded("调用频率超出限制，请稍后重试。")

        daily_usage = self._usage.increment(
            workspace_id=workspace_id,
            scope=UsageWindowScope.DAY,
            window_start=day_window,
            requests=1,
            tokens=token_estimate,
        )
        if daily_usage.request_count > quota_limit:
            raise RateLimitExceeded("调用次数已达每日配额。")

    def _record_rate_limit_event(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        deployment_id: int,
        model_version_id: int,
        api_key_id: int | None,
        user_id: int | None,
        request_payload: dict[str, Any],
        token_estimate: int,
        message: str,
    ) -> None:
        with self._transaction():
            self._calls.create(
                workspace_id=workspace_id,
                project_id=project_id,
                deployment_id=deployment_id,
                model_version_id=model_version_id,
                api_key_id=api_key_id,
                user_id=user_id,
                request_payload=request_payload,
                response_payload=None,
                status=InferenceCallStatus.RATE_LIMITED,
                latency_ms=None,
                input_tokens=token_estimate,
                output_tokens=None,
                error_message=message,
            )
        self._audits.record(
            event_type="inference.rate_limited",
            user_id=user_id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace_id,
                "deployment_id": deployment_id,
                "model_version_id": model_version_id,
                "api_key_id": api_key_id,
                "message": message,
            },
        )

    @staticmethod
    def _estimate_tokens(values: Iterable[str]) -> int:
        total_chars = sum(len(value) for value in values)
        return max(1, total_chars // 4)

    @staticmethod
    def _generate_stub_outputs(
        deployment: Deployment,
        inputs: list[str],
        parameters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        trace = parameters or {}
        temperature = trace.get("temperature", 0.7)
        outputs: list[dict[str, Any]] = []
        for index, text in enumerate(inputs):
            generated = f"[deployment:{deployment.id}] 温度={temperature:.2f} → {text.strip()} :: 响应 {index + 1}"
            outputs.append({"output": generated})
        return outputs

    # ------------------------------------------------------------------ #
    # API key utilities
    # ------------------------------------------------------------------ #

    def authenticate_api_key(self, raw_key: str) -> InferenceApiKey | None:
        """Validate API key string, returning entity if active."""
        if not raw_key or len(raw_key) < 16:
            return None
        prefix = raw_key[:16]
        api_key = self._api_keys.get_active_by_prefix(prefix)
        if api_key is None:
            return None
        if not verify_api_key(raw_key, api_key.key_hash):
            return None
        return api_key

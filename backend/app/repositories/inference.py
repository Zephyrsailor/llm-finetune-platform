"""Repositories for inference related persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlmodel import Session

from app.models import (
    InferenceApiKey,
    InferenceCall,
    InferenceCallStatus,
    InferenceUsage,
    UsageWindowScope,
)


class InferenceCallRepository:
    """Persist and query inference call records."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        deployment_id: int | None,
        model_version_id: int | None,
        api_key_id: int | None,
        user_id: int | None,
        request_payload: dict | None,
        response_payload: dict | None,
        status: InferenceCallStatus,
        latency_ms: float | None,
        input_tokens: int | None,
        output_tokens: int | None,
        error_message: str | None,
    ) -> InferenceCall:
        entry = InferenceCall(
            workspace_id=workspace_id,
            project_id=project_id,
            deployment_id=deployment_id,
            model_version_id=model_version_id,
            api_key_id=api_key_id,
            user_id=user_id,
            request_payload=request_payload,
            response_payload=response_payload,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error_message=error_message,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def list_for_workspace(
        self,
        *,
        workspace_id: int,
        limit: int = 50,
    ) -> Sequence[InferenceCall]:
        statement = (
            select(InferenceCall)
            .where(InferenceCall.workspace_id == workspace_id)
            .order_by(InferenceCall.created_at.desc())
            .limit(limit)
        )
        return tuple(self._session.exec(statement).scalars().all())

    def list_since(
        self,
        *,
        workspace_id: int,
        since: datetime,
        deployment_id: int | None = None,
    ) -> Sequence[InferenceCall]:
        statement = (
            select(InferenceCall)
            .where(
                InferenceCall.workspace_id == workspace_id,
                InferenceCall.created_at >= since,
            )
            .order_by(InferenceCall.created_at.desc())
        )
        if deployment_id is not None:
            statement = statement.where(InferenceCall.deployment_id == deployment_id)
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, call_id: int) -> InferenceCall | None:
        return self._session.get(InferenceCall, call_id)


class InferenceUsageRepository:
    """Store aggregated usage counters for rate limiting and quotas."""

    def __init__(self, session: Session):
        self._session = session

    def _get_for_update(
        self,
        *,
        workspace_id: int,
        scope: UsageWindowScope,
        window_start: datetime,
    ) -> InferenceUsage | None:
        statement = (
            select(InferenceUsage)
            .where(
                InferenceUsage.workspace_id == workspace_id,
                InferenceUsage.scope == scope,
                InferenceUsage.window_start == window_start,
            )
        )
        return self._session.exec(statement).scalars().first()

    def increment(
        self,
        *,
        workspace_id: int,
        scope: UsageWindowScope,
        window_start: datetime,
        requests: int,
        tokens: int,
    ) -> InferenceUsage:
        usage = self._get_for_update(
            workspace_id=workspace_id,
            scope=scope,
            window_start=window_start,
        )
        if usage is None:
            usage = InferenceUsage(
                workspace_id=workspace_id,
                scope=scope,
                window_start=window_start,
                request_count=requests,
                token_count=tokens,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self._session.add(usage)
        else:
            usage.request_count += requests
            usage.token_count += tokens
            usage.updated_at = datetime.utcnow()
        self._session.flush()
        self._session.refresh(usage)
        return usage

    def list_for_workspace(
        self,
        *,
        workspace_id: int,
        scope: UsageWindowScope | None = None,
        since: datetime | None = None,
    ) -> Sequence[InferenceUsage]:
        statement = select(InferenceUsage).where(InferenceUsage.workspace_id == workspace_id)
        if scope is not None:
            statement = statement.where(InferenceUsage.scope == scope)
        if since is not None:
            statement = statement.where(InferenceUsage.window_start >= since)
        statement = statement.order_by(InferenceUsage.window_start.desc())
        return tuple(self._session.exec(statement).scalars().all())


class InferenceApiKeyRepository:
    """Manage inference API keys."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        *,
        workspace_id: int,
        name: str,
        key_prefix: str,
        key_hash: str,
        rate_limit_per_minute: int | None,
        daily_quota: int | None,
        created_by: int | None,
    ) -> InferenceApiKey:
        api_key = InferenceApiKey(
            workspace_id=workspace_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            rate_limit_per_minute=rate_limit_per_minute,
            daily_quota=daily_quota,
            created_by=created_by,
        )
        self._session.add(api_key)
        self._session.flush()
        self._session.refresh(api_key)
        return api_key

    def get_active_by_prefix(self, key_prefix: str) -> InferenceApiKey | None:
        statement = select(InferenceApiKey).where(
            InferenceApiKey.key_prefix == key_prefix,
            InferenceApiKey.is_active.is_(True),
        )
        return self._session.exec(statement).scalars().first()

    def get(self, api_key_id: int) -> InferenceApiKey | None:
        return self._session.get(InferenceApiKey, api_key_id)

    def list_for_workspace(self, workspace_id: int) -> Sequence[InferenceApiKey]:
        statement = (
            select(InferenceApiKey)
            .where(InferenceApiKey.workspace_id == workspace_id)
            .order_by(InferenceApiKey.created_at.desc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def revoke(self, api_key: InferenceApiKey) -> InferenceApiKey:
        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.updated_at = datetime.utcnow()
        self._session.add(api_key)
        self._session.flush()
        self._session.refresh(api_key)
        return api_key

    def mark_used(self, api_key: InferenceApiKey) -> None:
        api_key.last_used_at = datetime.utcnow()
        api_key.updated_at = datetime.utcnow()
        self._session.add(api_key)
        self._session.flush()

"""Notification center service logic."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlmodel import Session

from app.models import (
    NotificationChannel,
    NotificationChannelType,
    NotificationDeliveryStatus,
    NotificationRecord,
)
from app.repositories.notification import (
    NotificationChannelRepository,
    NotificationRecordRepository,
)
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import AccessDeniedError
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


class NotificationService:
    """Manage notification channels and dispatch events."""

    _ALLOWED_EVENT_TYPES: tuple[str, ...] = (
        "training.job.completed",
        "training.job.alert",
        "deployment.status.changed",
        "governance.comment.created",
        "governance.comment.mention",
        "governance.approval.requested",
        "governance.approval.completed",
        "governance.kanban.reminder",
    )
    _MAX_ATTEMPTS = 2
    _RETRY_DELAY = timedelta(minutes=5)
    _DEFAULT_EMAIL_SUBJECT = "【LLMFT】平台事件提醒"
    _UNSET = object()

    def __init__(
        self,
        session: Session,
        *,
        http_client: httpx.Client | None = None,
    ):
        self._session = session
        self._channels = NotificationChannelRepository(session)
        self._records = NotificationRecordRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._permissions = PermissionService(session)
        self._http_client = http_client

    # ------------------------------------------------------------------ #
    # Channel management
    # ------------------------------------------------------------------ #

    def list_channels(self, workspace_id: int, *, current_user) -> list[NotificationChannel]:
        self._require_manage(workspace_id=workspace_id, user=current_user)
        return list(self._channels.list_for_workspace(workspace_id))

    def create_channel(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        name: str,
        channel_type: NotificationChannelType,
        event_types: Iterable[str],
        config: dict[str, Any],
        is_active: bool,
        current_user,
    ) -> NotificationChannel:
        self._require_manage(workspace_id=workspace_id, user=current_user)
        if not self._workspaces.is_member(workspace_id, current_user.id):
            raise AccessDeniedError("没有访问该工作空间的权限")
        normalized_types = self._normalize_event_types(event_types)
        channel = self._channels.create(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            channel_type=channel_type,
            event_types=normalized_types,
            config=self._sanitize_config(channel_type, config),
            is_active=is_active,
            created_by=current_user.id,
        )
        self._session.commit()
        return channel

    def update_channel(
        self,
        *,
        channel_id: int,
        name: str | None,
        event_types: Iterable[str] | None,
        config: dict[str, Any] | None,
        is_active: bool | None,
        project_id: int | None | object,
        current_user,
    ) -> NotificationChannel:
        channel = self._channels.get(channel_id)
        if channel is None:
            raise LookupError("通知渠道不存在")
        self._require_manage(workspace_id=channel.workspace_id, user=current_user)
        if name is not None:
            channel.name = name
        if project_id is not self._UNSET:
            channel.project_id = project_id  # type: ignore[assignment]
        if event_types is not None:
            channel.event_types = self._normalize_event_types(event_types)
        if config is not None:
            channel.config = self._sanitize_config(channel.channel_type, config)
        if is_active is not None:
            channel.is_active = is_active
        self._channels.save(channel, updated_by=current_user.id)
        self._session.commit()
        return channel

    def delete_channel(
        self,
        *,
        channel_id: int,
        current_user,
    ) -> None:
        channel = self._channels.get(channel_id)
        if channel is None:
            raise LookupError("通知渠道不存在")
        self._require_manage(workspace_id=channel.workspace_id, user=current_user)
        self._channels.delete(channel)
        self._session.commit()

    # ------------------------------------------------------------------ #
    # Event dispatch
    # ------------------------------------------------------------------ #

    def enqueue_event(
        self,
        *,
        workspace_id: int,
        event_type: str,
        payload: dict[str, Any] | None,
        project_id: int | None = None,
        actor_id: int | None = None,
    ) -> list[NotificationRecord]:
        normalized_event = self._normalize_event_type(event_type)
        candidate_channels = [
            channel
            for channel in self._channels.list_for_workspace(workspace_id)
            if channel.is_active and normalized_event in channel.event_types
        ]
        if not candidate_channels:
            return []
        enriched_payload = dict(payload or {})
        if actor_id is not None:
            enriched_payload.setdefault("actor_id", actor_id)
        records: list[NotificationRecord] = []
        for channel in candidate_channels:
            record = self._records.create(
                workspace_id=workspace_id,
                project_id=project_id or channel.project_id,
                channel_id=channel.id,
                event_type=normalized_event,
                payload=enriched_payload,
                status=NotificationDeliveryStatus.PENDING,
            )
            records.append(record)
            self._attempt_delivery(record, channel)
        self._session.commit()
        return records

    def list_events(self, *, workspace_id: int, current_user, limit: int | None = None) -> list[NotificationRecord]:
        self._require_manage(workspace_id=workspace_id, user=current_user)
        return list(self._records.list_for_workspace(workspace_id, limit=limit))

    def retry_event(
        self,
        *,
        record_id: int,
        current_user,
    ) -> NotificationRecord:
        record = self._records.get(record_id)
        if record is None:
            raise LookupError("通知记录不存在")
        self._require_manage(workspace_id=record.workspace_id, user=current_user)
        channel = self._channels.get(record.channel_id)
        if channel is None or channel.workspace_id != record.workspace_id:
            raise LookupError("通知渠道不存在")
        record.status = NotificationDeliveryStatus.PENDING
        record.attempts = 0
        record.last_error = None
        record.next_retry_at = None
        record.dispatched_at = None
        self._records.save(record)
        self._attempt_delivery(record, channel)
        self._session.commit()
        return record

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _attempt_delivery(self, record: NotificationRecord, channel: NotificationChannel) -> None:
        for _ in range(self._MAX_ATTEMPTS):
            try:
                self._deliver_once(record, channel)
                record.status = NotificationDeliveryStatus.SENT
                record.dispatched_at = datetime.utcnow()
                record.next_retry_at = None
                record.last_error = None
                self._records.save(record)
                return
            except Exception as exc:  # noqa: BLE001 - we need to capture transport errors
                record.attempts += 1
                record.status = NotificationDeliveryStatus.FAILED
                record.last_error = str(exc)
                record.next_retry_at = datetime.utcnow() + self._RETRY_DELAY
                self._records.save(record)
        # Exhausted attempts; leave record as FAILED for manual intervention.

    def _deliver_once(self, record: NotificationRecord, channel: NotificationChannel) -> None:
        payload = record.payload or {}
        if channel.channel_type == NotificationChannelType.WEBHOOK:
            self._send_webhook(channel, record.event_type, payload)
        elif channel.channel_type == NotificationChannelType.IM:
            self._send_im(channel, record.event_type, payload)
        elif channel.channel_type == NotificationChannelType.EMAIL:
            self._send_email(channel, record.event_type, payload)
        else:  # pragma: no cover - defensive branch
            raise ValueError(f"Unsupported channel type: {channel.channel_type}")

    def _send_webhook(self, channel: NotificationChannel, event_type: str, payload: dict[str, Any]) -> None:
        url = str(channel.config.get("url", "")).strip()
        if not url:
            raise ValueError("Webhook 渠道必须配置 url")
        parsed = urlparse(url)
        if parsed.scheme == "file":
            target = Path(parsed.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps({"event_type": event_type, "payload": payload}, ensure_ascii=False)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content + "\n")
            return
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Webhook 渠道仅支持 http/https/file 协议")
        headers = channel.config.get("headers") or {}

        client = self._http_client
        if client is not None:
            response = client.post(
                url,
                json={
                    "event_type": event_type,
                    "payload": payload,
                },
                headers=headers,
            )
            response.raise_for_status()
            return

        with httpx.Client(timeout=10.0, trust_env=False) as temp_client:
            response = temp_client.post(
                url,
                json={
                    "event_type": event_type,
                    "payload": payload,
                },
                headers=headers,
            )
            response.raise_for_status()

    def _send_im(self, channel: NotificationChannel, event_type: str, payload: dict[str, Any]) -> None:
        message = payload.copy()
        message.setdefault(
            "text",
            f"[通知] 事件 {event_type} 已触发。",
        )
        transformed = {"event_type": event_type, "message": message}
        temp_channel = NotificationChannel(
            id=channel.id,
            workspace_id=channel.workspace_id,
            project_id=channel.project_id,
            name=channel.name,
            channel_type=NotificationChannelType.WEBHOOK,
            event_types=channel.event_types,
            config=channel.config,
            is_active=channel.is_active,
            created_by=channel.created_by,
            updated_by=channel.updated_by,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
        self._send_webhook(temp_channel, event_type, transformed)

    def _send_email(self, channel: NotificationChannel, event_type: str, payload: dict[str, Any]) -> None:
        config = channel.config
        recipients = config.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            raise ValueError("Email 渠道需配置 recipients 列表")
        sender = str(config.get("sender") or "no-reply@llmft.local")
        subject = str(config.get("subject") or self._DEFAULT_EMAIL_SUBJECT)
        spool_dir_raw = str(config.get("spool_dir") or "tmp/notification_spool")
        spool_dir = Path(spool_dir_raw)
        if not spool_dir.is_absolute():
            spool_dir = Path.cwd() / spool_dir
        spool_dir.mkdir(parents=True, exist_ok=True)
        filename = spool_dir / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}_{channel.id}.eml"
        body = json.dumps(
            {
                "event_type": event_type,
                "payload": payload,
                "recipients": recipients,
            },
            ensure_ascii=False,
            indent=2,
        )
        message = (
            f"From: {sender}\n"
            f"To: {', '.join(recipients)}\n"
            f"Subject: {subject}\n"
            f"Date: {datetime.utcnow().isoformat()}Z\n"
            "\n"
            f"{body}\n"
        )
        filename.write_text(message, encoding="utf-8")

    def _normalize_event_types(self, event_types: Iterable[str]) -> list[str]:
        normalized = []
        for item in event_types:
            normalized.append(self._normalize_event_type(item))
        if not normalized:
            raise ValueError("至少需要选择一个事件类型")
        return sorted(set(normalized))

    def _normalize_event_type(self, event_type: str) -> str:
        candidate = str(event_type or "").strip()
        if candidate not in self._ALLOWED_EVENT_TYPES:
            raise ValueError("事件类型不受支持")
        return candidate

    def _sanitize_config(
        self,
        channel_type: NotificationChannelType,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(config, dict):
            raise ValueError("配置必须为对象类型")
        sanitized = dict(config)
        if channel_type in {NotificationChannelType.WEBHOOK, NotificationChannelType.IM}:
            url = str(sanitized.get("url") or "").strip()
            if not url:
                raise ValueError("Webhook/IM 渠道需配置 url")
            sanitized["url"] = url
            headers = sanitized.get("headers") or {}
            if headers and not isinstance(headers, dict):
                raise ValueError("headers 必须为字典")
        elif channel_type == NotificationChannelType.EMAIL:
            recipients = sanitized.get("recipients")
            if not isinstance(recipients, list) or not recipients:
                raise ValueError("Email 渠道需配置 recipients 列表")
            sanitized["recipients"] = [str(item).strip() for item in recipients if str(item).strip()]
            if not sanitized["recipients"]:
                raise ValueError("Email 渠道需配置有效的收件人")
            sender = str(sanitized.get("sender") or "no-reply@llmft.local").strip()
            sanitized["sender"] = sender
            subject = str(sanitized.get("subject") or self._DEFAULT_EMAIL_SUBJECT).strip()
            sanitized["subject"] = subject
            spool_dir = str(sanitized.get("spool_dir") or "tmp/notification_spool").strip()
            sanitized["spool_dir"] = spool_dir or "tmp/notification_spool"
        return sanitized

    def _require_manage(self, *, workspace_id: int, user) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )

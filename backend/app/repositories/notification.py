"""Repositories for notification center entities."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlmodel import Session

from app.models import NotificationChannel, NotificationRecord, NotificationDeliveryStatus


class NotificationChannelRepository:
    """Persist and query notification channels."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(self, workspace_id: int) -> Sequence[NotificationChannel]:
        statement = (
            select(NotificationChannel)
            .where(NotificationChannel.workspace_id == workspace_id)
            .order_by(NotificationChannel.created_at.asc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, channel_id: int) -> NotificationChannel | None:
        return self._session.get(NotificationChannel, channel_id)

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        name: str,
        channel_type,
        event_types: Iterable[str],
        config: dict,
        is_active: bool,
        created_by: int | None,
    ) -> NotificationChannel:
        channel = NotificationChannel(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            channel_type=channel_type,
            event_types=list(event_types),
            config=config,
            is_active=is_active,
            created_by=created_by,
            updated_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._session.add(channel)
        self._session.flush()
        self._session.refresh(channel)
        return channel

    def save(self, channel: NotificationChannel, *, updated_by: int | None) -> NotificationChannel:
        channel.updated_by = updated_by
        channel.updated_at = datetime.utcnow()
        self._session.add(channel)
        self._session.flush()
        self._session.refresh(channel)
        return channel

    def delete(self, channel: NotificationChannel) -> None:
        self._session.delete(channel)
        self._session.flush()


class NotificationRecordRepository:
    """Persistence helpers for notification delivery records."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_workspace(self, workspace_id: int, *, limit: int | None = None) -> Sequence[NotificationRecord]:
        statement = (
            select(NotificationRecord)
            .where(NotificationRecord.workspace_id == workspace_id)
            .order_by(NotificationRecord.created_at.desc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, record_id: int) -> NotificationRecord | None:
        return self._session.get(NotificationRecord, record_id)

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        channel_id: int,
        event_type: str,
        payload: dict | None,
        status: NotificationDeliveryStatus,
    ) -> NotificationRecord:
        record = NotificationRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            channel_id=channel_id,
            event_type=event_type,
            payload=payload,
            status=status,
            attempts=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def save(self, record: NotificationRecord) -> NotificationRecord:
        record.updated_at = datetime.utcnow()
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def list_pending(self, *, limit: int | None = None) -> Sequence[NotificationRecord]:
        statement = (
            select(NotificationRecord)
            .where(NotificationRecord.status == NotificationDeliveryStatus.PENDING)
            .order_by(NotificationRecord.created_at.asc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        return tuple(self._session.exec(statement).scalars().all())

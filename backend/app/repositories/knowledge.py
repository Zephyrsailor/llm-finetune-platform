"""Repositories handling knowledge entries and versions."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlmodel import Session

from app.models import KnowledgeEntry, KnowledgeEntryVersion, KnowledgeEntryType


class KnowledgeEntryRepository:
    """Provide persistence helpers for knowledge entries."""

    def __init__(self, session: Session):
        self._session = session

    def list(
        self,
        *,
        workspace_id: int,
        project_id: int | None = None,
        entry_type: KnowledgeEntryType | None = None,
    ) -> Sequence[KnowledgeEntry]:
        statement = select(KnowledgeEntry).where(
            KnowledgeEntry.workspace_id == workspace_id,
            KnowledgeEntry.is_active.is_(True),
        )
        if project_id is not None:
            statement = statement.where(KnowledgeEntry.project_id == project_id)
        if entry_type is not None:
            statement = statement.where(KnowledgeEntry.entry_type == entry_type)
        statement = statement.order_by(KnowledgeEntry.updated_at.desc())
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, entry_id: int) -> KnowledgeEntry | None:
        return self._session.get(KnowledgeEntry, entry_id)

    def create(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        entry_type: KnowledgeEntryType,
        title: str,
        description: str | None,
        tags: Iterable[str],
        created_by: int,
    ) -> KnowledgeEntry:
        now = datetime.utcnow()
        entry = KnowledgeEntry(
            workspace_id=workspace_id,
            project_id=project_id,
            entry_type=entry_type,
            title=title,
            description=description,
            tags=list(dict.fromkeys(tags)),
            latest_version=0,
            is_active=True,
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry

    def save(self, entry: KnowledgeEntry, *, updated_by: int | None = None) -> KnowledgeEntry:
        entry.updated_by = updated_by
        entry.updated_at = datetime.utcnow()
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return entry


class KnowledgeEntryVersionRepository:
    """Persist and retrieve knowledge entry versions."""

    def __init__(self, session: Session):
        self._session = session

    def list_for_entry(self, entry_id: int) -> Sequence[KnowledgeEntryVersion]:
        statement = (
            select(KnowledgeEntryVersion)
            .where(KnowledgeEntryVersion.entry_id == entry_id)
            .order_by(KnowledgeEntryVersion.version.desc())
        )
        return tuple(self._session.exec(statement).scalars().all())

    def get(self, version_id: int) -> KnowledgeEntryVersion | None:
        return self._session.get(KnowledgeEntryVersion, version_id)

    def create(
        self,
        *,
        entry_id: int,
        version: int,
        summary: str | None,
        content: str | None,
        config_snapshot: dict | None,
        storage_path: str | None,
        created_by: int,
    ) -> KnowledgeEntryVersion:
        payload = KnowledgeEntryVersion(
            entry_id=entry_id,
            version=version,
            summary=summary,
            content=content,
            config_snapshot=config_snapshot,
            storage_path=storage_path,
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        self._session.add(payload)
        self._session.flush()
        self._session.refresh(payload)
        return payload

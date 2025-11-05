"""Knowledge base service for documentation and template reuse."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlmodel import Session

from app.core.config import settings
from app.models import (
    KnowledgeEntry,
    KnowledgeEntryType,
    KnowledgeEntryVersion,
    User,
)
from app.repositories.audit import AuditLogRepository
from app.repositories.knowledge import KnowledgeEntryRepository, KnowledgeEntryVersionRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.errors import AccessDeniedError, TrainingValidationError
from app.services.permissions import PermissionService
from app.services.roles import RoleOperation


@dataclass(slots=True)
class KnowledgeEntryDetail:
    """Structured payload returned by knowledge service."""

    entry: KnowledgeEntry
    versions: list[KnowledgeEntryVersion]


class KnowledgeBaseService:
    """Provide APIs for storing and reusing knowledge artifacts."""

    _TEXT_EXTENSIONS: dict[KnowledgeEntryType, str] = {
        KnowledgeEntryType.DOCUMENT: "md",
        KnowledgeEntryType.SCRIPT: "txt",
        KnowledgeEntryType.TRAINING_TEMPLATE: "json",
        KnowledgeEntryType.EVALUATION_TEMPLATE: "json",
        KnowledgeEntryType.DEPLOYMENT_TEMPLATE: "json",
    }
    _TEMPLATE_TYPES = {
        KnowledgeEntryType.TRAINING_TEMPLATE,
        KnowledgeEntryType.EVALUATION_TEMPLATE,
        KnowledgeEntryType.DEPLOYMENT_TEMPLATE,
    }

    def __init__(self, session: Session):
        self._session = session
        self._entries = KnowledgeEntryRepository(session)
        self._versions = KnowledgeEntryVersionRepository(session)
        self._workspaces = WorkspaceRepository(session)
        self._permissions = PermissionService(session)
        self._audits = AuditLogRepository(session)

    # ------------------------------------------------------------------ #
    # Listing & retrieval
    # ------------------------------------------------------------------ #

    def list_entries(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        entry_type: KnowledgeEntryType | None,
        tag: str | None,
        current_user: User,
    ) -> list[KnowledgeEntry]:
        self._ensure_member(workspace_id=workspace_id, user=current_user)
        entries = list(
            self._entries.list(
                workspace_id=workspace_id,
                project_id=project_id,
                entry_type=entry_type,
            )
        )
        if tag:
            entries = [entry for entry in entries if tag in entry.tags]
        return entries

    def get_entry(self, entry_id: int, *, current_user: User) -> KnowledgeEntryDetail:
        entry = self._entries.get(entry_id)
        if entry is None or not entry.is_active:
            raise TrainingValidationError("知识条目不存在")
        self._ensure_member(workspace_id=entry.workspace_id, user=current_user)
        versions = list(self._versions.list_for_entry(entry.id))
        return KnowledgeEntryDetail(entry=entry, versions=versions)

    # ------------------------------------------------------------------ #
    # Create & update
    # ------------------------------------------------------------------ #

    def create_entry(
        self,
        *,
        workspace_id: int,
        project_id: int | None,
        entry_type: KnowledgeEntryType,
        title: str,
        description: str | None,
        tags: Iterable[str],
        content: str | None,
        config_snapshot: dict | None,
        summary: str | None,
        current_user: User,
    ) -> KnowledgeEntryDetail:
        self._require_manage(workspace_id=workspace_id, user=current_user)
        self._ensure_member(workspace_id=workspace_id, user=current_user)
        entry = self._entries.create(
            workspace_id=workspace_id,
            project_id=project_id,
            entry_type=entry_type,
            title=title,
            description=description,
            tags=tags,
            created_by=current_user.id,
        )
        version_payload = self._create_version_payload(
            entry=entry,
            version=1,
            summary=summary,
            content=content,
            config_snapshot=config_snapshot,
            actor_id=current_user.id,
        )
        entry.latest_version = 1
        self._entries.save(entry, updated_by=current_user.id)
        self._session.commit()
        self._audits.record(
            event_type="knowledge.entry.created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": workspace_id,
                "entry_id": entry.id,
                "entry_type": entry.entry_type.value,
            },
        )
        return KnowledgeEntryDetail(entry=entry, versions=[version_payload])

    def create_version(
        self,
        *,
        entry_id: int,
        summary: str | None,
        content: str | None,
        config_snapshot: dict | None,
        current_user: User,
    ) -> KnowledgeEntryDetail:
        entry_detail = self.get_entry(entry_id, current_user=current_user)
        entry = entry_detail.entry
        self._require_manage(workspace_id=entry.workspace_id, user=current_user)
        next_version = entry.latest_version + 1
        new_version = self._create_version_payload(
            entry=entry,
            version=next_version,
            summary=summary,
            content=content,
            config_snapshot=config_snapshot,
            actor_id=current_user.id,
        )
        entry.latest_version = next_version
        entry.updated_by = current_user.id
        entry.updated_at = datetime.utcnow()
        self._entries.save(entry, updated_by=current_user.id)
        self._session.commit()
        self._audits.record(
            event_type="knowledge.entry.version_created",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": entry.workspace_id,
                "entry_id": entry.id,
                "version": next_version,
            },
        )
        versions = [new_version] + list(entry_detail.versions)
        return KnowledgeEntryDetail(entry=entry, versions=versions)

    def clone_template(
        self,
        *,
        entry_id: int,
        target_project_id: int | None,
        title: str | None,
        current_user: User,
    ) -> KnowledgeEntryDetail:
        source = self.get_entry(entry_id, current_user=current_user)
        if source.entry.entry_type not in self._TEMPLATE_TYPES:
            raise TrainingValidationError("仅支持模板条目的复制")
        self._require_manage(workspace_id=source.entry.workspace_id, user=current_user)
        new_entry = self._entries.create(
            workspace_id=source.entry.workspace_id,
            project_id=target_project_id,
            entry_type=source.entry.entry_type,
            title=title or source.entry.title,
            description=source.entry.description,
            tags=source.entry.tags,
            created_by=current_user.id,
        )
        versions: list[KnowledgeEntryVersion] = []
        for version in sorted(source.versions, key=lambda item: item.version):
            cloned = self._create_version_payload(
                entry=new_entry,
                version=version.version if version.version > 0 else len(versions) + 1,
                summary=version.summary,
                content=version.content,
                config_snapshot=version.config_snapshot,
                actor_id=current_user.id,
                source_storage_path=version.storage_path,
            )
            versions.append(cloned)
            new_entry.latest_version = max(new_entry.latest_version, cloned.version)
        self._entries.save(new_entry, updated_by=current_user.id)
        self._session.commit()
        self._audits.record(
            event_type="knowledge.entry.cloned",
            user_id=current_user.id,
            ip_address=None,
            user_agent=None,
            payload={
                "workspace_id": new_entry.workspace_id,
                "entry_id": new_entry.id,
                "source_entry_id": source.entry.id,
                "target_project_id": target_project_id,
            },
        )
        versions.sort(key=lambda item: item.version, reverse=True)
        return KnowledgeEntryDetail(entry=new_entry, versions=versions)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _create_version_payload(
        self,
        *,
        entry: KnowledgeEntry,
        version: int,
        summary: str | None,
        content: str | None,
        config_snapshot: dict | None,
        actor_id: int,
        source_storage_path: str | None = None,
    ) -> KnowledgeEntryVersion:
        storage_path: str | None = None
        text_content = content
        config_content = config_snapshot

        if entry.entry_type in {KnowledgeEntryType.DOCUMENT, KnowledgeEntryType.SCRIPT}:
            if not text_content:
                raise TrainingValidationError("文档或脚本内容不能为空")
            storage_path = self._write_text_payload(entry, version, text_content)
        else:
            if config_content is None:
                raise TrainingValidationError("模板内容不能为空")
            storage_path = self._write_json_payload(entry, version, config_content)

        if source_storage_path and storage_path is None:
            storage_path = self._copy_storage(source_storage_path, entry, version)

        return self._versions.create(
            entry_id=entry.id,
            version=version,
            summary=summary,
            content=text_content if entry.entry_type in {KnowledgeEntryType.DOCUMENT, KnowledgeEntryType.SCRIPT} else None,
            config_snapshot=config_content if entry.entry_type in self._TEMPLATE_TYPES else None,
            storage_path=storage_path,
            created_by=actor_id,
        )

    def _copy_storage(self, source_path: str, entry: KnowledgeEntry, version: int) -> str:
        base = self._storage_root()
        origin = base / source_path
        if not origin.exists():
            return None
        target_dir = self._entry_directory(entry.workspace_id, entry.project_id, entry.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        ext = origin.suffix or ".json"
        target = target_dir / f"v{version}{ext}"
        target.write_bytes(origin.read_bytes())
        return str(target.relative_to(base))

    def _write_text_payload(self, entry: KnowledgeEntry, version: int, content: str) -> str:
        extension = self._TEXT_EXTENSIONS.get(entry.entry_type, "txt")
        target_dir = self._entry_directory(entry.workspace_id, entry.project_id, entry.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"v{version}.{extension}"
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self._storage_root()))

    def _write_json_payload(self, entry: KnowledgeEntry, version: int, payload: dict[str, Any]) -> str:
        target_dir = self._entry_directory(entry.workspace_id, entry.project_id, entry.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"v{version}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target.relative_to(self._storage_root()))

    def _entry_directory(self, workspace_id: int, project_id: int | None, entry_id: int) -> Path:
        workspace_segment = str(workspace_id)
        project_segment = str(project_id) if project_id is not None else "general"
        return self._storage_root() / workspace_segment / project_segment / "knowledge" / "library" / f"entry-{entry_id}"

    def _storage_root(self) -> Path:
        return Path(settings.workspace_storage_root).expanduser()

    def _ensure_member(self, *, workspace_id: int, user: User) -> None:
        if not self._workspaces.is_member(workspace_id, user.id):
            raise AccessDeniedError("没有访问该工作空间的权限")

    def _require_manage(self, *, workspace_id: int, user: User) -> None:
        self._permissions.require_operation(
            workspace_id=workspace_id,
            user=user,
            operation=RoleOperation.APPROVAL_MANAGE,
            ip_address=None,
            user_agent=None,
        )

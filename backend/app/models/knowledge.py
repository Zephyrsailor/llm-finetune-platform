"""Knowledge base models for reusable templates and documentation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, Enum, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class KnowledgeEntryType(StrEnum):
    """Supported knowledge entry categories."""

    DOCUMENT = "document"
    SCRIPT = "script"
    TRAINING_TEMPLATE = "training_template"
    EVALUATION_TEMPLATE = "evaluation_template"
    DEPLOYMENT_TEMPLATE = "deployment_template"


class KnowledgeEntry(SQLModel, table=True):
    """Top-level knowledge entry metadata."""

    __tablename__ = "knowledge_entries"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    entry_type: KnowledgeEntryType = Field(
        sa_column=Column(Enum(KnowledgeEntryType, name="knowledge_entry_type_enum"), nullable=False)
    )
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    latest_version: int = Field(default=0, nullable=False)
    is_active: bool = Field(default=True)
    created_by: int = Field(foreign_key="users.id", index=True)
    updated_by: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class KnowledgeEntryVersion(SQLModel, table=True):
    """Versioned content for knowledge entries."""

    __tablename__ = "knowledge_entry_versions"
    __table_args__ = (
        UniqueConstraint("entry_id", "version", name="uq_knowledge_entry_version"),
    )

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="knowledge_entries.id", index=True)
    version: int = Field(nullable=False)
    summary: str | None = Field(default=None, max_length=1000)
    content: str | None = Field(default=None)
    config_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    storage_path: str | None = Field(default=None, max_length=1024)
    created_by: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

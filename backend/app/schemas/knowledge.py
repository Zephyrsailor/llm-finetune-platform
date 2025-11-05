"""Pydantic schemas for knowledge base APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import KnowledgeEntryType


class KnowledgeEntryVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    version: int
    summary: str | None = None
    content: str | None = None
    config_snapshot: dict[str, Any] | None = None
    storage_path: str | None = None
    created_by: int
    created_at: datetime


class KnowledgeEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    workspace_id: int
    project_id: int | None = None
    entry_type: KnowledgeEntryType
    title: str
    description: str | None = None
    tags: list[str]
    latest_version: int
    is_active: bool
    created_by: int
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeEntryDetailResponse(BaseModel):
    entry: KnowledgeEntryResponse
    versions: list[KnowledgeEntryVersionResponse]


class KnowledgeEntryCreateRequest(BaseModel):
    workspace_id: int
    project_id: int | None = None
    entry_type: KnowledgeEntryType
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    config_snapshot: dict[str, Any] | None = None


class KnowledgeEntryVersionCreateRequest(BaseModel):
    summary: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    config_snapshot: dict[str, Any] | None = None


class KnowledgeTemplateCloneRequest(BaseModel):
    target_project_id: int | None = None
    title: str | None = Field(default=None, max_length=200)

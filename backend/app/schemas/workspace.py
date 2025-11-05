"""Workspace API request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models import ProjectStatus, WorkspaceStatus


class WorkspaceMemberInfo(BaseModel):
    user_id: int
    email: str
    role: str


class ProjectInfo(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    plan: Optional[str] = None
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceDetail(WorkspaceBase):
    members: List[WorkspaceMemberInfo]
    projects: List[ProjectInfo]
    model_config = {"from_attributes": True}


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    plan: Optional[str] = Field(default=None, max_length=64)
    member_ids: List[int] = Field(default_factory=list, description="额外成员的用户 ID 列表")


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    plan: Optional[str] = Field(default=None, max_length=64)
    status: Optional[WorkspaceStatus] = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)


class ProjectCreateResponse(BaseModel):
    workspace: WorkspaceDetail
    created_paths: List[str]

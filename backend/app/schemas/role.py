"""Role-related API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.roles import RoleOperation, ROLE_OPERATION_LABELS


class RoleSummary(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    is_system: bool
    operations: List[str]


class RoleOperationOption(BaseModel):
    value: str
    label: str


class RoleAssignmentSummary(BaseModel):
    user_id: int
    email: str
    role_ids: List[int]


class RoleMatrixResponse(BaseModel):
    roles: List[RoleSummary]
    assignments: List[RoleAssignmentSummary]
    operations: List[RoleOperationOption]


class RoleCreateRequest(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    operations: List[str] = Field(..., description="角色拥有的权限操作列表")

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("至少需要选择一个权限操作")
        allowed = {operation.value for operation in RoleOperation}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"存在未定义的权限操作: {', '.join(unknown)}")
        return sorted(set(value))


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    operations: Optional[List[str]] = Field(default=None, description="角色拥有的权限操作列表")

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        if not value:
            raise ValueError("至少需要选择一个权限操作")
        allowed = {operation.value for operation in RoleOperation}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"存在未定义的权限操作: {', '.join(unknown)}")
        return sorted(set(value))


class RoleAssignmentRequest(BaseModel):
    role_ids: List[int] = Field(default_factory=list, description="要分配给成员的角色 ID 列表")


def build_role_operation_options() -> list[RoleOperationOption]:
    """Helper used by API layer to convert enum labels."""
    return [
        RoleOperationOption(value=operation.value, label=ROLE_OPERATION_LABELS[operation])
        for operation in RoleOperation
    ]

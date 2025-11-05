"""Role matrix helpers and default definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict

from app.repositories.role import RoleRepository


class RoleOperation(StrEnum):
    """Operations controlled by workspace role assignments."""

    DATA_IMPORT = "data_import"
    TRAINING_LAUNCH = "training_launch"
    DEPLOYMENT_MANAGE = "deployment_manage"
    EVALUATION_VIEW = "evaluation_view"
    APPROVAL_MANAGE = "approval_manage"
    INFERENCE_USE = "inference_use"


ROLE_OPERATION_LABELS: dict[RoleOperation, str] = {
    RoleOperation.DATA_IMPORT: "数据导入与治理",
    RoleOperation.TRAINING_LAUNCH: "训练任务发起",
    RoleOperation.DEPLOYMENT_MANAGE: "部署与运维",
    RoleOperation.EVALUATION_VIEW: "评估结果查看",
    RoleOperation.APPROVAL_MANAGE: "审批与治理操作",
    RoleOperation.INFERENCE_USE: "推理 API 调用",
}


@dataclass(frozen=True, slots=True)
class DefaultRoleDefinition:
    """Default role metadata and permissions."""

    key: str
    name: str
    description: str
    operations: tuple[RoleOperation, ...]


DEFAULT_ROLE_MATRIX: tuple[DefaultRoleDefinition, ...] = (
    DefaultRoleDefinition(
        key="workspace-admin",
        name="管理员",
        description="拥有工作空间内的全部管理权限，可配置角色与成员、执行全量操作。",
        operations=(
            RoleOperation.DATA_IMPORT,
            RoleOperation.TRAINING_LAUNCH,
            RoleOperation.DEPLOYMENT_MANAGE,
            RoleOperation.EVALUATION_VIEW,
            RoleOperation.APPROVAL_MANAGE,
            RoleOperation.INFERENCE_USE,
        ),
    ),
    DefaultRoleDefinition(
        key="data-steward",
        name="数据角色",
        description="负责数据导入与治理，具备数据操作与评估查看权限。",
        operations=(
            RoleOperation.DATA_IMPORT,
            RoleOperation.EVALUATION_VIEW,
        ),
    ),
    DefaultRoleDefinition(
        key="training-engineer",
        name="训练角色",
        description="负责模型训练执行，可发起训练并查看评估结果。",
        operations=(
            RoleOperation.TRAINING_LAUNCH,
            RoleOperation.EVALUATION_VIEW,
            RoleOperation.INFERENCE_USE,
        ),
    ),
    DefaultRoleDefinition(
        key="operations-engineer",
        name="运维角色",
        description="负责部署上线和运行维护，可管理部署并查看评估信息。",
        operations=(
            RoleOperation.DEPLOYMENT_MANAGE,
            RoleOperation.EVALUATION_VIEW,
            RoleOperation.INFERENCE_USE,
        ),
    ),
    DefaultRoleDefinition(
        key="business-reviewer",
        name="业务审阅角色",
        description="聚焦业务合规与审批，具备审批处理与评估查看权限。",
        operations=(
            RoleOperation.APPROVAL_MANAGE,
            RoleOperation.EVALUATION_VIEW,
        ),
    ),
    DefaultRoleDefinition(
        key="application-developer",
        name="应用集成角色",
        description="负责在业务系统中调用平台推理服务，具备推理调用与指标查看权限。",
        operations=(
            RoleOperation.INFERENCE_USE,
            RoleOperation.EVALUATION_VIEW,
        ),
    ),
)


def ensure_default_roles(role_repo: RoleRepository, workspace_id: int) -> Dict[str, int]:
    """Ensure default roles exist for the workspace and return id mapping."""
    role_ids: Dict[str, int] = {}
    for definition in DEFAULT_ROLE_MATRIX:
        role = role_repo.upsert_role(
            workspace_id=workspace_id,
            key=definition.key,
            name=definition.name,
            description=definition.description,
            is_system=True,
        )
        role_repo.set_role_operations(
            role_id=role.id,
            operations=[operation.value for operation in definition.operations],
        )
        role_ids[definition.key] = role.id
    return role_ids


def list_role_operation_options() -> list[dict[str, str]]:
    """Return value/label pairs for available role operations."""
    return [
        {"value": operation.value, "label": ROLE_OPERATION_LABELS[operation]}
        for operation in RoleOperation
    ]

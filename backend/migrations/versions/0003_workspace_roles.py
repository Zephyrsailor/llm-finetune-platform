"""Introduce workspace role matrix tables.

Revision ID: 0003_workspace_roles
Revises: 0002_workspace_project
Create Date: 2025-10-29
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_workspace_roles"
down_revision: Union[str, None] = "0002_workspace_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "key", name="uq_roles_workspace_key"),
    )
    op.create_index("ix_roles_workspace_id", "roles", ["workspace_id"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("role_id", "operation", name="pk_role_permissions"),
    )

    op.create_table(
        "workspace_member_roles",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("workspace_id", "user_id", "role_id", name="pk_workspace_member_roles"),
    )
    op.create_index(
        "ix_workspace_member_roles_role_id",
        "workspace_member_roles",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_member_roles_user_id",
        "workspace_member_roles",
        ["user_id"],
        unique=False,
    )

    # Seed default roles for existing workspaces (if any).
    bind = op.get_bind()
    workspaces_table = sa.table(
        "workspaces",
        sa.column("id", sa.Integer),
        sa.column("created_by", sa.Integer),
    )
    members_table = sa.table(
        "workspace_members",
        sa.column("workspace_id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("role", sa.String(length=32)),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("workspace_id", sa.Integer),
        sa.column("key", sa.String(length=64)),
        sa.column("name", sa.String(length=128)),
        sa.column("description", sa.String(length=512)),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=False)),
        sa.column("updated_at", sa.DateTime(timezone=False)),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("operation", sa.String(length=64)),
        sa.column("created_at", sa.DateTime(timezone=False)),
    )
    member_roles_table = sa.table(
        "workspace_member_roles",
        sa.column("workspace_id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
        sa.column("assigned_at", sa.DateTime(timezone=False)),
    )

    default_roles = (
        {
            "key": "workspace-admin",
            "name": "管理员",
            "description": "拥有工作空间内的全部管理权限，可配置角色与成员、执行全量操作。",
            "operations": (
                "data_import",
                "training_launch",
                "deployment_manage",
                "evaluation_view",
                "approval_manage",
            ),
            "assign_owner": True,
        },
        {
            "key": "data-steward",
            "name": "数据角色",
            "description": "负责数据导入与治理，具备数据操作与评估查看权限。",
            "operations": (
                "data_import",
                "evaluation_view",
            ),
            "assign_owner": False,
        },
        {
            "key": "training-engineer",
            "name": "训练角色",
            "description": "负责模型训练执行，可发起训练并查看评估结果。",
            "operations": (
                "training_launch",
                "evaluation_view",
            ),
            "assign_owner": False,
        },
        {
            "key": "operations-engineer",
            "name": "运维角色",
            "description": "负责部署上线和运行维护，可管理部署并查看评估信息。",
            "operations": (
                "deployment_manage",
                "evaluation_view",
            ),
            "assign_owner": False,
        },
        {
            "key": "business-reviewer",
            "name": "业务审阅角色",
            "description": "聚焦业务合规与审批，具备审批处理与评估查看权限。",
            "operations": (
                "approval_manage",
                "evaluation_view",
            ),
            "assign_owner": False,
        },
    )

    workspace_rows = list(bind.execute(sa.select(workspaces_table.c.id, workspaces_table.c.created_by)))
    if workspace_rows:
        now = datetime.utcnow()
        for workspace_id, created_by in workspace_rows:
            role_id_map: dict[str, int] = {}
            for role_def in default_roles:
                result = bind.execute(
                    roles_table.insert().values(
                        workspace_id=workspace_id,
                        key=role_def["key"],
                        name=role_def["name"],
                        description=role_def["description"],
                        is_system=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                role_id = result.inserted_primary_key[0]
                if role_id is None:
                    role_id = bind.execute(
                        sa.select(roles_table.c.id).where(
                            roles_table.c.workspace_id == workspace_id,
                            roles_table.c.key == role_def["key"],
                        )
                    ).scalar_one()
                role_id_map[role_def["key"]] = role_id

                if role_def["operations"]:
                    bind.execute(
                        role_permissions_table.insert(),
                        [
                            {
                                "role_id": role_id,
                                "operation": operation,
                                "created_at": now,
                            }
                            for operation in role_def["operations"]
                        ],
                    )

            admin_role_id = role_id_map.get("workspace-admin")
            if admin_role_id is None:
                continue

            owner_rows = list(
                bind.execute(
                    sa.select(members_table.c.user_id).where(
                        members_table.c.workspace_id == workspace_id,
                        members_table.c.role == "owner",
                    )
                )
            )
            owner_user_ids = [row.user_id for row in owner_rows]
            if not owner_user_ids and created_by is not None:
                owner_user_ids = [created_by]

            if owner_user_ids:
                bind.execute(
                    member_roles_table.insert(),
                    [
                        {
                            "workspace_id": workspace_id,
                            "user_id": owner_id,
                            "role_id": admin_role_id,
                            "assigned_at": now,
                        }
                        for owner_id in owner_user_ids
                    ],
                )


def downgrade() -> None:
    op.drop_index("ix_workspace_member_roles_user_id", table_name="workspace_member_roles")
    op.drop_index("ix_workspace_member_roles_role_id", table_name="workspace_member_roles")
    op.drop_table("workspace_member_roles")
    op.drop_table("role_permissions")
    op.drop_index("ix_roles_workspace_id", table_name="roles")
    op.drop_table("roles")

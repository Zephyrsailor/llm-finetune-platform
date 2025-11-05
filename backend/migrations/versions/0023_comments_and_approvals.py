"""Add governance comments and approval workflows.

Revision ID: 0023_comments_and_approvals
Revises: 0022_governance_kanban
Create Date: 2025-11-05 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0023_comments_and_approvals"
down_revision = "0022_governance_kanban"
branch_labels = None
depends_on = None


comment_entity_type_enum = sa.Enum(
    "dataset_version",
    "training_job",
    "evaluation_job",
    "deployment",
    name="comment_entity_type_enum",
)

approval_status_enum = sa.Enum(
    "pending",
    "approved",
    "rejected",
    name="approval_status_enum",
)

approval_task_status_enum = sa.Enum(
    "pending",
    "approved",
    "rejected",
    name="approval_task_status_enum",
)


def upgrade() -> None:
    comment_entity_type_enum.create(op.get_bind(), checkfirst=True)
    approval_status_enum.create(op.get_bind(), checkfirst=True)
    approval_task_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "governance_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", comment_entity_type_enum, nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=4000), nullable=False),
        sa.Column("mentions", sa.JSON(), nullable=False, server_default=sa.text("[]")),
        sa.Column("attachments", sa.JSON(), nullable=False, server_default=sa.text("[]")),
        sa.Column("context", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_comments_workspace_entity",
        "governance_comments",
        ["workspace_id", "entity_type", "entity_id"],
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", comment_entity_type_enum, nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", approval_status_enum, nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_requests_workspace_entity",
        "approval_requests",
        ["workspace_id", "entity_type", "entity_id"],
    )

    op.create_table(
        "approval_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", approval_task_status_enum, nullable=False, server_default="pending"),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_tasks_request_approver",
        "approval_tasks",
        ["request_id", "approver_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_tasks_request_approver", table_name="approval_tasks")
    op.drop_table("approval_tasks")

    op.drop_index("ix_approval_requests_workspace_entity", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_governance_comments_workspace_entity", table_name="governance_comments")
    op.drop_table("governance_comments")

    approval_task_status_enum.drop(op.get_bind(), checkfirst=True)
    approval_status_enum.drop(op.get_bind(), checkfirst=True)
    # comment_entity_type_enum is shared by governance models; keep for downward compatibility

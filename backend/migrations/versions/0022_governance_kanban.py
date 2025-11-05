"""Create kanban tables for governance module.

Revision ID: 0022_governance_kanban
Revises: 0021_runtime_monitoring
Create Date: 2025-11-05 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0022_governance_kanban"
down_revision = "0021_runtime_monitoring"
branch_labels = None
depends_on = None


kanban_stage_enum = sa.Enum(
    "data",
    "training",
    "evaluation",
    "deployment",
    name="kanban_stage_enum",
)

kanban_status_enum = sa.Enum(
    "backlog",
    "in_progress",
    "blocked",
    "done",
    name="kanban_status_enum",
)

kanban_entity_type_enum = sa.Enum(
    "generic",
    "dataset_version",
    "training_job",
    "evaluation_job",
    "deployment",
    name="kanban_entity_type_enum",
)


def upgrade() -> None:
    kanban_stage_enum.create(op.get_bind(), checkfirst=True)
    kanban_status_enum.create(op.get_bind(), checkfirst=True)
    kanban_entity_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "kanban_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", kanban_stage_enum, nullable=False),
        sa.Column("status", kanban_status_enum, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("order_index", sa.Float(), nullable=False),
        sa.Column("entity_type", kanban_entity_type_enum, nullable=False, server_default="generic"),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_minutes_before", sa.Integer(), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kanban_cards_workspace_stage_status",
        "kanban_cards",
        ["workspace_id", "stage", "status"],
    )
    op.create_index(
        "ix_kanban_cards_entity",
        "kanban_cards",
        ["workspace_id", "entity_type", "entity_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_kanban_cards_entity", table_name="kanban_cards")
    op.drop_index("ix_kanban_cards_workspace_stage_status", table_name="kanban_cards")
    op.drop_table("kanban_cards")

    kanban_entity_type_enum.drop(op.get_bind(), checkfirst=True)
    kanban_status_enum.drop(op.get_bind(), checkfirst=True)
    kanban_stage_enum.drop(op.get_bind(), checkfirst=True)

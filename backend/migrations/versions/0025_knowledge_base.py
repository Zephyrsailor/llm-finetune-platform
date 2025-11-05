"""Create knowledge base tables.

Revision ID: 0025_knowledge_base
Revises: 0024_notification_center
Create Date: 2025-11-06 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0025_knowledge_base"
down_revision = "0024_notification_center"
branch_labels = None
depends_on = None


knowledge_entry_type_enum = sa.Enum(
    "document",
    "script",
    "training_template",
    "evaluation_template",
    "deployment_template",
    name="knowledge_entry_type_enum",
)


def upgrade() -> None:
    knowledge_entry_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", knowledge_entry_type_enum, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("[]")),
        sa.Column("latest_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_entries_workspace_id",
        "knowledge_entries",
        ["workspace_id"],
    )
    op.create_index(
        "ix_knowledge_entries_project_id",
        "knowledge_entries",
        ["project_id"],
    )

    op.create_table(
        "knowledge_entry_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("knowledge_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "version", name="uq_knowledge_entry_version"),
    )
    op.create_index(
        "ix_knowledge_entry_versions_entry_id",
        "knowledge_entry_versions",
        ["entry_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_entry_versions_entry_id", table_name="knowledge_entry_versions")
    op.drop_table("knowledge_entry_versions")

    op.drop_index("ix_knowledge_entries_project_id", table_name="knowledge_entries")
    op.drop_index("ix_knowledge_entries_workspace_id", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")

    knowledge_entry_type_enum.drop(op.get_bind(), checkfirst=True)

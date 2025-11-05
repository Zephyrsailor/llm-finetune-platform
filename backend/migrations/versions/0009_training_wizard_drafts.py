"""Add training wizard drafts table.

Revision ID: 0009_training_wizard_drafts
Revises: 0008_training_templates
Create Date: 2025-10-31 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_training_wizard_drafts"
down_revision = "0008_training_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_wizard_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_training_wizard_drafts_scope"),
    )
    op.create_index(
        "ix_training_wizard_drafts_workspace_id",
        "training_wizard_drafts",
        ["workspace_id"],
    )
    op.create_index(
        "ix_training_wizard_drafts_user_id",
        "training_wizard_drafts",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_training_wizard_drafts_user_id", table_name="training_wizard_drafts")
    op.drop_index("ix_training_wizard_drafts_workspace_id", table_name="training_wizard_drafts")
    op.drop_table("training_wizard_drafts")

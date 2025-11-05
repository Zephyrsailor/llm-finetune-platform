"""Add notification center tables.

Revision ID: 0024_notification_center
Revises: 0023_comments_and_approvals
Create Date: 2025-11-06 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0024_notification_center"
down_revision = "0023_comments_and_approvals"
branch_labels = None
depends_on = None


notification_channel_type_enum = sa.Enum(
    "webhook",
    "email",
    "im",
    name="notification_channel_type_enum",
)

notification_delivery_status_enum = sa.Enum(
    "pending",
    "sent",
    "failed",
    name="notification_delivery_status_enum",
)


def upgrade() -> None:
    notification_channel_type_enum.create(op.get_bind(), checkfirst=True)
    notification_delivery_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("channel_type", notification_channel_type_enum, nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False, server_default=sa.text("[]")),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("{}")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_channels_workspace_id",
        "notification_channels",
        ["workspace_id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", notification_delivery_status_enum, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_workspace_id",
        "notifications",
        ["workspace_id"],
    )
    op.create_index(
        "ix_notifications_event_type",
        "notifications",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_workspace_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_notification_channels_workspace_id", table_name="notification_channels")
    op.drop_table("notification_channels")

    notification_delivery_status_enum.drop(op.get_bind(), checkfirst=True)
    notification_channel_type_enum.drop(op.get_bind(), checkfirst=True)

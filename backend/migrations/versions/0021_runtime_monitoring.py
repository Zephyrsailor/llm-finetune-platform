"""Add runtime monitoring alert tables.

Revision ID: 0021_runtime_monitoring
Revises: 0020_inference_api
Create Date: 2025-11-05 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0021_runtime_monitoring"
down_revision = "0020_inference_api"
branch_labels = None
depends_on = None


runtime_metric_name = sa.Enum(
    "qps",
    "latency_p95_ms",
    "error_rate",
    "token_throughput_per_minute",
    "gpu_memory_mb",
    "gpu_utilization",
    name="runtime_metric_name",
)

runtime_alert_operator = sa.Enum(
    "gt",
    "gte",
    "lt",
    "lte",
    name="runtime_alert_operator",
)

runtime_alert_status = sa.Enum(
    "triggered",
    "acknowledged",
    "resolved",
    name="runtime_alert_status",
)


def upgrade() -> None:
    runtime_metric_name.create(op.get_bind(), checkfirst=True)
    runtime_alert_operator.create(op.get_bind(), checkfirst=True)
    runtime_alert_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "runtime_alert_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("metric", runtime_metric_name, nullable=False),
        sa.Column("operator", runtime_alert_operator, nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("channels_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_runtime_alert_rules_workspace_id",
        "runtime_alert_rules",
        ["workspace_id"],
    )
    op.create_index(
        "ix_runtime_alert_rules_deployment_id",
        "runtime_alert_rules",
        ["deployment_id"],
    )

    op.create_table(
        "runtime_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("runtime_alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("status", runtime_alert_status, nullable=False, server_default="triggered"),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("recommendation", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_runtime_alerts_workspace_id",
        "runtime_alerts",
        ["workspace_id"],
    )
    op.create_index(
        "ix_runtime_alerts_deployment_id",
        "runtime_alerts",
        ["deployment_id"],
    )
    op.create_index(
        "ix_runtime_alerts_triggered_at",
        "runtime_alerts",
        ["triggered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_alerts_triggered_at", table_name="runtime_alerts")
    op.drop_index("ix_runtime_alerts_deployment_id", table_name="runtime_alerts")
    op.drop_index("ix_runtime_alerts_workspace_id", table_name="runtime_alerts")
    op.drop_table("runtime_alerts")

    op.drop_index("ix_runtime_alert_rules_deployment_id", table_name="runtime_alert_rules")
    op.drop_index("ix_runtime_alert_rules_workspace_id", table_name="runtime_alert_rules")
    op.drop_table("runtime_alert_rules")

    runtime_alert_status.drop(op.get_bind(), checkfirst=True)
    runtime_alert_operator.drop(op.get_bind(), checkfirst=True)
    runtime_metric_name.drop(op.get_bind(), checkfirst=True)

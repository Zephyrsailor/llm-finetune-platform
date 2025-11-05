"""Add training monitoring tables for metrics and alerts.

Revision ID: 0011_training_monitoring
Revises: 0010_training_job_resources
Create Date: 2025-10-31 18:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_training_monitoring"
down_revision = "0010_training_job_resources"
branch_labels = None
depends_on = None


training_metric_name = sa.Enum(
    "LOSS",
    "PERPLEXITY",
    "THROUGHPUT",
    "GPU_MEMORY",
    name="training_metric_name",
)

training_alert_metric = sa.Enum(
    "LOSS",
    "PERPLEXITY",
    "THROUGHPUT",
    "GPU_MEMORY",
    name="training_alert_metric",
)

training_alert_operator = sa.Enum(
    "GREATER_THAN",
    "GREATER_OR_EQUAL",
    "LESS_THAN",
    "LESS_OR_EQUAL",
    name="training_alert_operator",
)

training_alert_status = sa.Enum(
    "TRIGGERED",
    "ACKNOWLEDGED",
    "RESOLVED",
    name="training_alert_status",
)


def upgrade() -> None:
    training_metric_name.create(op.get_bind(), checkfirst=True)
    training_alert_metric.create(op.get_bind(), checkfirst=True)
    training_alert_operator.create(op.get_bind(), checkfirst=True)
    training_alert_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "training_metric_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("training_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", training_metric_name, nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_training_metric_samples_run_id",
        "training_metric_samples",
        ["run_id"],
    )
    op.create_index(
        "ix_training_metric_samples_recorded_at",
        "training_metric_samples",
        ["recorded_at"],
    )

    op.create_table(
        "training_alert_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("metric", training_alert_metric, nullable=False),
        sa.Column("operator", training_alert_operator, nullable=False),
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
        "ix_training_alert_rules_workspace_id",
        "training_alert_rules",
        ["workspace_id"],
    )

    op.create_table(
        "training_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("training_alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("training_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("status", training_alert_status, nullable=False, server_default="TRIGGERED"),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_training_alerts_rule_id",
        "training_alerts",
        ["rule_id"],
    )
    op.create_index(
        "ix_training_alerts_run_id",
        "training_alerts",
        ["run_id"],
    )
    op.create_index(
        "ix_training_alerts_triggered_at",
        "training_alerts",
        ["triggered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_training_alerts_triggered_at", table_name="training_alerts")
    op.drop_index("ix_training_alerts_run_id", table_name="training_alerts")
    op.drop_index("ix_training_alerts_rule_id", table_name="training_alerts")
    op.drop_table("training_alerts")

    op.drop_index("ix_training_alert_rules_workspace_id", table_name="training_alert_rules")
    op.drop_table("training_alert_rules")

    op.drop_index("ix_training_metric_samples_recorded_at", table_name="training_metric_samples")
    op.drop_index("ix_training_metric_samples_run_id", table_name="training_metric_samples")
    op.drop_table("training_metric_samples")

    training_alert_status.drop(op.get_bind(), checkfirst=True)
    training_alert_operator.drop(op.get_bind(), checkfirst=True)
    training_alert_metric.drop(op.get_bind(), checkfirst=True)
    training_metric_name.drop(op.get_bind(), checkfirst=True)

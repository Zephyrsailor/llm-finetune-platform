"""Add training snapshots table and resume metadata.

Revision ID: 0012_training_snapshots
Revises: 0011_training_monitoring
Create Date: 2025-10-31 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0012_training_snapshots"
down_revision = "0011_training_monitoring"
branch_labels = None
depends_on = None


training_snapshot_trigger = sa.Enum(
    "SCHEDULED",
    "METRIC",
    "MANUAL",
    name="training_snapshot_trigger_type",
)


def upgrade() -> None:
    training_snapshot_trigger.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "training_runs",
        sa.Column("resumed_from_snapshot_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_training_runs_resumed_from_snapshot_id",
        "training_runs",
        ["resumed_from_snapshot_id"],
    )

    op.create_table(
        "training_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("training_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("step", sa.Integer(), nullable=True),
        sa.Column("epoch", sa.Integer(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("trigger_type", training_snapshot_trigger, nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.Column("restored_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_snapshots_workspace", "training_snapshots", ["workspace_id"])
    op.create_index("ix_training_snapshots_run", "training_snapshots", ["run_id"])
    op.create_index("ix_training_snapshots_job", "training_snapshots", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_training_snapshots_job", table_name="training_snapshots")
    op.drop_index("ix_training_snapshots_run", table_name="training_snapshots")
    op.drop_index("ix_training_snapshots_workspace", table_name="training_snapshots")
    op.drop_table("training_snapshots")

    op.drop_index("ix_training_runs_resumed_from_snapshot_id", table_name="training_runs")
    op.drop_column("training_runs", "resumed_from_snapshot_id")

    training_snapshot_trigger.drop(op.get_bind(), checkfirst=True)

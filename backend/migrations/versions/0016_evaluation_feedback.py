"""Add evaluation feedback table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_evaluation_feedback"
down_revision = "0015_evaluation_automation"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    feedback_status_enum = sa.Enum(
        "open",
        "resolved",
        name="evaluation_feedback_status",
    )
    feedback_kind_enum = sa.Enum(
        "comment",
        "todo",
        "business_metric",
        name="evaluation_feedback_kind",
    )
    feedback_status_enum.create(op.get_bind(), checkfirst=True)
    feedback_kind_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("evaluation_job_id", sa.Integer(), sa.ForeignKey("evaluation_jobs.id"), nullable=False),
        sa.Column("training_run_id", sa.Integer(), sa.ForeignKey("training_runs.id"), nullable=True),
        sa.Column("kind", feedback_kind_enum, nullable=False, server_default="comment"),
        sa.Column("status", feedback_status_enum, nullable=False, server_default="open"),
        sa.Column("body", sa.String(length=4096), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metric_name", sa.String(length=200), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index("ix_evaluation_feedback_workspace_id", "evaluation_feedback", ["workspace_id"])
    op.create_index("ix_evaluation_feedback_project_id", "evaluation_feedback", ["project_id"])
    op.create_index("ix_evaluation_feedback_job_id", "evaluation_feedback", ["evaluation_job_id"])
    op.create_index("ix_evaluation_feedback_training_run_id", "evaluation_feedback", ["training_run_id"])
    op.create_index("ix_evaluation_feedback_kind", "evaluation_feedback", ["kind"])
    op.create_index("ix_evaluation_feedback_status", "evaluation_feedback", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_feedback_status", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_kind", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_training_run_id", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_job_id", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_project_id", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_workspace_id", table_name="evaluation_feedback")
    op.drop_table("evaluation_feedback")

    feedback_status_enum = sa.Enum(name="evaluation_feedback_status")
    feedback_kind_enum = sa.Enum(name="evaluation_feedback_kind")
    feedback_status_enum.drop(op.get_bind(), checkfirst=True)
    feedback_kind_enum.drop(op.get_bind(), checkfirst=True)

"""Add evaluation templates and jobs tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_evaluation_tables"
down_revision = "0013_training_run_metadata"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("task_type", sa.Enum("question_answering", "conversation", "classification", name="evaluation_task_type"), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index("ix_evaluation_templates_key", "evaluation_templates", ["key"], unique=True)
    op.create_index("ix_evaluation_templates_workspace_id", "evaluation_templates", ["workspace_id"])

    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("training_run_id", sa.Integer(), sa.ForeignKey("training_runs.id"), nullable=True),
        sa.Column("evaluation_template_id", sa.Integer(), sa.ForeignKey("evaluation_templates.id"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("dataset_path", sa.String(length=1024), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("report_path", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", name="evaluation_job_status"), nullable=False, server_default="pending"),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index("ix_evaluation_jobs_workspace_id", "evaluation_jobs", ["workspace_id"])
    op.create_index("ix_evaluation_jobs_project_id", "evaluation_jobs", ["project_id"])
    op.create_index("ix_evaluation_jobs_training_run_id", "evaluation_jobs", ["training_run_id"])
    op.create_index("ix_evaluation_jobs_dataset_version_id", "evaluation_jobs", ["dataset_version_id"])
    op.create_index("ix_evaluation_jobs_created_by", "evaluation_jobs", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_jobs_created_by", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_dataset_version_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_training_run_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_project_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_workspace_id", table_name="evaluation_jobs")
    op.drop_table("evaluation_jobs")
    op.drop_index("ix_evaluation_templates_workspace_id", table_name="evaluation_templates")
    op.drop_index("ix_evaluation_templates_key", table_name="evaluation_templates")
    op.drop_table("evaluation_templates")

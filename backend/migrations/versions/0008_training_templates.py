"""Add training template and job tables.

Revision ID: 0008_training_templates
Revises: 0007_format_versions
Create Date: 2025-10-31 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_training_templates"
down_revision = "0007_format_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    adapter_enum = sa.Enum(
        "lora",
        "qlora",
        "dora",
        "full-finetune",
        name="training_adapter_type",
    )
    job_adapter_enum = sa.Enum(
        "lora",
        "qlora",
        "dora",
        "full-finetune",
        name="training_job_adapter_type",
    )
    job_status_enum = sa.Enum(
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "canceled",
        name="training_job_status",
    )
    run_status_enum = sa.Enum(
        "pending",
        "queued",
        "running",
        "completed",
        "failed",
        "canceled",
        name="training_run_status",
    )

    bind = op.get_bind()
    adapter_enum.create(bind, checkfirst=True)
    job_adapter_enum.create(bind, checkfirst=True)
    job_status_enum.create(bind, checkfirst=True)
    run_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "training_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("base_model", sa.String(length=300), nullable=False),
        sa.Column("adapter_type", adapter_enum, nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_templates_workspace_id", "training_templates", ["workspace_id"])
    op.create_index("ix_training_templates_name", "training_templates", ["name"])
    op.create_index("ix_training_templates_created_by", "training_templates", ["created_by"])

    op.create_table(
        "training_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "dataset_format_version_id",
            sa.Integer(),
            sa.ForeignKey("dataset_format_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "training_template_id",
            sa.Integer(),
            sa.ForeignKey("training_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("base_model", sa.String(length=300), nullable=False),
        sa.Column("adapter_type", job_adapter_enum, nullable=False),
        sa.Column("status", job_status_enum, nullable=False, server_default="pending"),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("scheduled_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_jobs_workspace_id", "training_jobs", ["workspace_id"])
    op.create_index("ix_training_jobs_project_id", "training_jobs", ["project_id"])
    op.create_index("ix_training_jobs_dataset_version_id", "training_jobs", ["dataset_version_id"])
    op.create_index("ix_training_jobs_dataset_format_version_id", "training_jobs", ["dataset_format_version_id"])
    op.create_index("ix_training_jobs_training_template_id", "training_jobs", ["training_template_id"])
    op.create_index("ix_training_jobs_scheduled_by", "training_jobs", ["scheduled_by"])

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", run_status_enum, nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_runs_job_id", "training_runs", ["job_id"])

    op.create_table(
        "training_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("training_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="INFO"),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_events_run_id", "training_events", ["run_id"])
    op.create_index("ix_training_events_timestamp", "training_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_training_events_timestamp", table_name="training_events")
    op.drop_index("ix_training_events_run_id", table_name="training_events")
    op.drop_table("training_events")

    op.drop_index("ix_training_runs_job_id", table_name="training_runs")
    op.drop_table("training_runs")

    op.drop_index("ix_training_jobs_scheduled_by", table_name="training_jobs")
    op.drop_index("ix_training_jobs_training_template_id", table_name="training_jobs")
    op.drop_index("ix_training_jobs_dataset_format_version_id", table_name="training_jobs")
    op.drop_index("ix_training_jobs_dataset_version_id", table_name="training_jobs")
    op.drop_index("ix_training_jobs_project_id", table_name="training_jobs")
    op.drop_index("ix_training_jobs_workspace_id", table_name="training_jobs")
    op.drop_table("training_jobs")

    op.drop_index("ix_training_templates_created_by", table_name="training_templates")
    op.drop_index("ix_training_templates_name", table_name="training_templates")
    op.drop_index("ix_training_templates_workspace_id", table_name="training_templates")
    op.drop_table("training_templates")

    bind = op.get_bind()
    sa.Enum(name="training_run_status").drop(bind, checkfirst=True)
    sa.Enum(name="training_job_status").drop(bind, checkfirst=True)
    sa.Enum(name="training_job_adapter_type").drop(bind, checkfirst=True)
    sa.Enum(name="training_adapter_type").drop(bind, checkfirst=True)

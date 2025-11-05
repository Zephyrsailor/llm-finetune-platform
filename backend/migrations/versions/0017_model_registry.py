"""Add model registry tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0017_model_registry"
down_revision = "0016_evaluation_feedback"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    model_version_status = sa.Enum(
        "candidate",
        "production",
        "deprecated",
        name="model_version_status",
    )
    model_version_status.create(op.get_bind(), checkfirst=True)

    registered_models = op.create_table(
        "registered_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("base_model", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_registered_model_name"),
    )

    model_versions = op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", model_version_status, nullable=False, server_default="candidate"),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("training_run_id", sa.Integer(), sa.ForeignKey("training_runs.id"), nullable=True),
        sa.Column("evaluation_job_id", sa.Integer(), sa.ForeignKey("evaluation_jobs.id"), nullable=True),
        sa.Column("evaluation_metrics_json", sa.JSON(), nullable=True),
        sa.Column("evaluation_report_path", sa.String(length=1024), nullable=True),
        sa.Column("deployment_target", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("promoted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("model_id", "version", name="uq_model_version_number"),
    )

    op.create_index("ix_registered_models_workspace_id", "registered_models", ["workspace_id"])
    op.create_index("ix_registered_models_project_id", "registered_models", ["project_id"])
    op.create_index("ix_registered_models_created_by", "registered_models", ["created_by"])
    op.create_index("ix_registered_models_updated_by", "registered_models", ["updated_by"])

    op.create_index("ix_model_versions_model_id", "model_versions", ["model_id"])
    op.create_index("ix_model_versions_training_run_id", "model_versions", ["training_run_id"])
    op.create_index("ix_model_versions_evaluation_job_id", "model_versions", ["evaluation_job_id"])
    op.create_index("ix_model_versions_created_by", "model_versions", ["created_by"])
    op.create_index("ix_model_versions_updated_by", "model_versions", ["updated_by"])
    op.create_index("ix_model_versions_promoted_by", "model_versions", ["promoted_by"])


def downgrade() -> None:
    op.drop_index("ix_model_versions_promoted_by", table_name="model_versions")
    op.drop_index("ix_model_versions_updated_by", table_name="model_versions")
    op.drop_index("ix_model_versions_created_by", table_name="model_versions")
    op.drop_index("ix_model_versions_evaluation_job_id", table_name="model_versions")
    op.drop_index("ix_model_versions_training_run_id", table_name="model_versions")
    op.drop_index("ix_model_versions_model_id", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index("ix_registered_models_updated_by", table_name="registered_models")
    op.drop_index("ix_registered_models_created_by", table_name="registered_models")
    op.drop_index("ix_registered_models_project_id", table_name="registered_models")
    op.drop_index("ix_registered_models_workspace_id", table_name="registered_models")
    op.drop_table("registered_models")

    model_version_status = sa.Enum(name="model_version_status")
    model_version_status.drop(op.get_bind(), checkfirst=True)

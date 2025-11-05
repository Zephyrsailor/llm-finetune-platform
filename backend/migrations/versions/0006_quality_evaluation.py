"""Add quality evaluation job tables and dataset version fields.

Revision ID: 0006_quality_evaluation
Revises: 0005_cleaning_templates
Create Date: 2025-10-30 14:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_quality_evaluation"
down_revision = "0005_cleaning_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quality_evaluation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", name="quality_evaluation_status"), nullable=False),
        sa.Column("logs_path", sa.String(length=1024), nullable=True),
        sa.Column("summary_path", sa.String(length=1024), nullable=True),
        sa.Column("export_manifest", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "ix_quality_evaluation_jobs_dataset_version_id",
        "quality_evaluation_jobs",
        ["dataset_version_id"],
    )

    op.add_column("dataset_versions", sa.Column("quality_summary_path", sa.String(length=1024), nullable=True))
    op.add_column("dataset_versions", sa.Column("quality_report_manifest", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_quality_evaluation_jobs_dataset_version_id", table_name="quality_evaluation_jobs")
    op.drop_column("dataset_versions", "quality_report_manifest")
    op.drop_column("dataset_versions", "quality_summary_path")
    op.drop_table("quality_evaluation_jobs")

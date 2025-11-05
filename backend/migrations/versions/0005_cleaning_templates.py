"""Add dataset cleaning templates and enrich cleaning jobs.

Revision ID: 0005_cleaning_templates
Revises: 0004_datahub_tables
Create Date: 2025-10-30 12:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_cleaning_templates"
down_revision = "0004_datahub_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_cleaning_templates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_dataset_cleaning_templates_workspace_id",
        "dataset_cleaning_templates",
        ["workspace_id"],
    )

    op.create_table(
        "dataset_cleaning_assignments",
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), primary_key=True, nullable=False),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("dataset_cleaning_templates.id"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
    )

    op.add_column("data_cleaning_jobs", sa.Column("template_id", sa.Integer(), nullable=True))
    op.add_column("data_cleaning_jobs", sa.Column("template_snapshot", sa.JSON(), nullable=True))
    op.add_column("data_cleaning_jobs", sa.Column("summary_path", sa.String(length=1024), nullable=True))
    op.add_column("data_cleaning_jobs", sa.Column("export_manifest", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_data_cleaning_jobs_template",
        "data_cleaning_jobs",
        "dataset_cleaning_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_data_cleaning_jobs_template", "data_cleaning_jobs", type_="foreignkey")
    op.drop_column("data_cleaning_jobs", "export_manifest")
    op.drop_column("data_cleaning_jobs", "summary_path")
    op.drop_column("data_cleaning_jobs", "template_snapshot")
    op.drop_column("data_cleaning_jobs", "template_id")
    op.drop_table("dataset_cleaning_assignments")
    op.drop_index("ix_dataset_cleaning_templates_workspace_id", table_name="dataset_cleaning_templates")
    op.drop_table("dataset_cleaning_templates")

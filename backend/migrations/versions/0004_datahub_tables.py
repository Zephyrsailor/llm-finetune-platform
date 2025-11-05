"""Introduce dataset ingestion and cleaning tables.

Revision ID: 0004_datahub_tables
Revises: 0003_workspace_roles
Create Date: 2025-10-30
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_datahub_tables"
down_revision: Union[str, None] = "0003_workspace_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dataset_source_enum = sa.Enum(
        "upload",
        "external",
        "reference",
        name="dataset_source_type",
    )
    dataset_status_enum = sa.Enum(
        "active",
        "archived",
        name="dataset_status",
    )
    dataset_version_status_enum = sa.Enum(
        "pending",
        "processing",
        "completed",
        "failed",
        name="dataset_version_status",
    )
    data_cleaning_job_status_enum = sa.Enum(
        "pending",
        "running",
        "completed",
        "failed",
        name="data_cleaning_job_status",
    )

    dataset_source_enum.create(op.get_bind(), checkfirst=True)
    dataset_status_enum.create(op.get_bind(), checkfirst=True)
    dataset_version_status_enum.create(op.get_bind(), checkfirst=True)
    data_cleaning_job_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("source_type", dataset_source_enum, nullable=False, server_default="upload"),
        sa.Column("source_uri", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("data_type", sa.String(length=100), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", dataset_status_enum, nullable=False, server_default="active"),
        sa.Column("reference_dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "name", name="uq_datasets_workspace_name"),
    )
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"], unique=False)
    op.create_index("ix_datasets_name", "datasets", ["name"], unique=False)

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", dataset_version_status_enum, nullable=False, server_default="pending"),
        sa.Column("location_uri", sa.String(length=1024), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_version"),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"], unique=False)

    op.create_table(
        "data_cleaning_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", data_cleaning_job_status_enum, nullable=False, server_default="pending"),
        sa.Column("logs_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index("ix_data_cleaning_jobs_dataset_version_id", "data_cleaning_jobs", ["dataset_version_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_cleaning_jobs_dataset_version_id", table_name="data_cleaning_jobs")
    op.drop_table("data_cleaning_jobs")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_name", table_name="datasets")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_table("datasets")

    data_cleaning_job_status_enum = sa.Enum(name="data_cleaning_job_status")
    dataset_version_status_enum = sa.Enum(name="dataset_version_status")
    dataset_status_enum = sa.Enum(name="dataset_status")
    dataset_source_enum = sa.Enum(name="dataset_source_type")

    for enum in (
        data_cleaning_job_status_enum,
        dataset_version_status_enum,
        dataset_status_enum,
        dataset_source_enum,
    ):
        enum.drop(op.get_bind(), checkfirst=True)

"""Add dataset format version artefact tracking.

Revision ID: 0007_format_versions
Revises: 0006_quality_evaluation
Create Date: 2025-10-30 16:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_format_versions"
down_revision = "0006_quality_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    format_type_enum = sa.Enum(
        "jsonl",
        "sft",
        "parquet",
        name="dataset_format_type",
    )
    format_status_enum = sa.Enum(
        "pending",
        "running",
        "completed",
        "failed",
        name="dataset_format_status",
    )

    bind = op.get_bind()
    format_type_enum.create(bind, checkfirst=True)
    format_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "dataset_format_versions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "dataset_version_id",
            sa.Integer(),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", format_type_enum, nullable=False),
        sa.Column("status", format_status_enum, nullable=False, server_default="pending"),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("logs_path", sa.String(length=1024), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_dataset_format_versions_dataset_version_id",
        "dataset_format_versions",
        ["dataset_version_id"],
    )
    op.create_index(
        "ix_dataset_format_versions_active",
        "dataset_format_versions",
        ["dataset_version_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_format_versions_active", table_name="dataset_format_versions")
    op.drop_index(
        "ix_dataset_format_versions_dataset_version_id",
        table_name="dataset_format_versions",
    )
    op.drop_table("dataset_format_versions")

    format_status_enum = sa.Enum(name="dataset_format_status")
    format_type_enum = sa.Enum(name="dataset_format_type")
    bind = op.get_bind()
    format_status_enum.drop(bind, checkfirst=True)
    format_type_enum.drop(bind, checkfirst=True)

"""Add resource configuration fields for training jobs.

Revision ID: 0010_training_job_resources
Revises: 0009_training_wizard_drafts
Create Date: 2025-10-31 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_training_job_resources"
down_revision = "0009_training_wizard_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_jobs",
        sa.Column("requested_gpus", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "training_jobs",
        sa.Column("queue_name", sa.String(length=100), nullable=False, server_default="default"),
    )
    op.execute("UPDATE training_jobs SET requested_gpus = 1 WHERE requested_gpus IS NULL")
    op.execute("UPDATE training_jobs SET queue_name = 'default' WHERE queue_name IS NULL")
    op.alter_column("training_jobs", "requested_gpus", server_default=None)
    op.alter_column("training_jobs", "queue_name", server_default=None)


def downgrade() -> None:
    op.drop_column("training_jobs", "queue_name")
    op.drop_column("training_jobs", "requested_gpus")

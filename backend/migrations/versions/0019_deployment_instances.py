"""Add deployment_instances table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0019_deployment_instances"
down_revision = "0018_deployment_pipeline"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    deployment_status = sa.Enum(
        "pending",
        "deploying",
        "active",
        "failed",
        "rolled_back",
        name="deployment_status",
    )
    # enum already created in 0018, ensure it exists
    deployment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "deployment_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deployment_id",
            sa.Integer(),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(length=128), nullable=False),
        sa.Column("status", deployment_status, nullable=False, server_default="pending"),
        sa.Column("endpoint_url", sa.String(length=512), nullable=True),
        sa.Column("access_token", sa.String(length=512), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("traffic_percent", sa.Float(), nullable=True),
        sa.Column("health_checked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index(
        "ix_deployment_instances_deployment_id",
        "deployment_instances",
        ["deployment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_deployment_instances_deployment_id", table_name="deployment_instances")
    op.drop_table("deployment_instances")

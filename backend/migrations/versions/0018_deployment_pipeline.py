"""Add deployment tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_deployment_pipeline"
down_revision = "0017_model_registry"
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
    deployment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("model_version_id", sa.Integer(), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("environment", sa.String(length=128), nullable=False),
        sa.Column("status", deployment_status, nullable=False, server_default="pending"),
        sa.Column("endpoint_url", sa.String(length=512), nullable=True),
        sa.Column("access_token", sa.String(length=512), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("traffic_percent", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index("ix_deployments_workspace_id", "deployments", ["workspace_id"])
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])
    op.create_index("ix_deployments_model_version_id", "deployments", ["model_version_id"])

    op.create_table(
        "deployment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index("ix_deployment_events_deployment_id", "deployment_events", ["deployment_id"])


def downgrade() -> None:
    op.drop_index("ix_deployment_events_deployment_id", table_name="deployment_events")
    op.drop_table("deployment_events")

    op.drop_index("ix_deployments_model_version_id", table_name="deployments")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_index("ix_deployments_workspace_id", table_name="deployments")
    op.drop_table("deployments")

    deployment_status = sa.Enum(name="deployment_status")
    deployment_status.drop(op.get_bind(), checkfirst=True)

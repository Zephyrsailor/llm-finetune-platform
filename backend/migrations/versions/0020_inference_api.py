"""Add inference API tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0020_inference_api"
down_revision = "0019_deployment_instances"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    inference_call_status = sa.Enum(
        "success",
        "failed",
        "rate_limited",
        name="inference_call_status",
    )
    usage_scope = sa.Enum(
        "minute",
        "day",
        name="usage_window_scope",
    )

    inference_call_status.create(op.get_bind(), checkfirst=True)
    usage_scope.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "inference_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False, index=True),
        sa.Column("key_hash", sa.String(length=512), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("daily_quota", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("key_prefix", name="uq_inference_api_keys_prefix"),
    )
    op.create_index("ix_inference_api_keys_workspace_id", "inference_api_keys", ["workspace_id"])

    op.create_table(
        "inference_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("scope", usage_scope, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=False), nullable=False, index=True),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("workspace_id", "scope", "window_start", name="uq_inference_usage_window"),
    )

    op.create_table(
        "inference_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("deployments.id"), nullable=True, index=True),
        sa.Column("model_version_id", sa.Integer(), sa.ForeignKey("model_versions.id"), nullable=True, index=True),
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("inference_api_keys.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("status", inference_call_status, nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
    )
    op.create_index("ix_inference_calls_workspace_id", "inference_calls", ["workspace_id"])
    op.create_index("ix_inference_calls_deployment_id", "inference_calls", ["deployment_id"])
    op.create_index("ix_inference_calls_model_version_id", "inference_calls", ["model_version_id"])


def downgrade() -> None:
    op.drop_index("ix_inference_calls_model_version_id", table_name="inference_calls")
    op.drop_index("ix_inference_calls_deployment_id", table_name="inference_calls")
    op.drop_index("ix_inference_calls_workspace_id", table_name="inference_calls")
    op.drop_table("inference_calls")
    op.drop_table("inference_usage")
    op.drop_index("ix_inference_api_keys_workspace_id", table_name="inference_api_keys")
    op.drop_table("inference_api_keys")

    inference_call_status = sa.Enum(name="inference_call_status")
    usage_scope = sa.Enum(name="usage_window_scope")
    inference_call_status.drop(op.get_bind(), checkfirst=True)
    usage_scope.drop(op.get_bind(), checkfirst=True)

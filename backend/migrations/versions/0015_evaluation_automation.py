"""Enhance evaluation automation metadata and alert enums.

Revision ID: 0015_evaluation_automation
Revises: 0014_evaluation_tables
Create Date: 2025-10-31 19:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_evaluation_automation"
down_revision = "0014_evaluation_tables"
branch_labels = None
depends_on = None


evaluation_trigger_mode = sa.Enum("manual", "automatic", name="evaluation_trigger_mode")

_metric_values = (
    "LOSS",
    "PERPLEXITY",
    "THROUGHPUT",
    "GPU_MEMORY",
    "EVALUATION_BLEU",
    "EVALUATION_ROUGE_L",
    "EVALUATION_EXACT_MATCH",
    "EVALUATION_PERPLEXITY",
    "EVALUATION_FAILURE",
)

new_training_metric_name = sa.Enum(*_metric_values, name="training_metric_name", create_type=False)
new_training_alert_metric = sa.Enum(*_metric_values, name="training_alert_metric", create_type=False)


def _upgrade_enum_values(connection, enum_name: str, values: tuple[str, ...]) -> None:
    if connection.dialect.name != "postgresql":  # pragma: no cover - handled separately
        return
    for value in values:
        connection.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    bind = op.get_bind()

    evaluation_trigger_mode.create(bind, checkfirst=True)
    op.add_column(
        "evaluation_jobs",
        sa.Column("trigger_mode", evaluation_trigger_mode, nullable=False, server_default="manual"),
    )
    op.alter_column("evaluation_jobs", "trigger_mode", server_default=None)

    _upgrade_enum_values(bind, "training_metric_name", _metric_values)
    _upgrade_enum_values(bind, "training_alert_metric", _metric_values)

    if bind.dialect.name != "postgresql":  # SQLite path uses batch operations
        with op.batch_alter_table("training_metric_samples") as batch:
            batch.alter_column(
                "metric",
                existing_type=sa.Enum(
                    "LOSS",
                    "PERPLEXITY",
                    "THROUGHPUT",
                    "GPU_MEMORY",
                    name="training_metric_name",
                ),
                type_=new_training_metric_name,
                existing_nullable=False,
            )

        with op.batch_alter_table("training_alert_rules") as batch:
            batch.alter_column(
                "metric",
                existing_type=sa.Enum(
                    "LOSS",
                    "PERPLEXITY",
                    "THROUGHPUT",
                    "GPU_MEMORY",
                    name="training_alert_metric",
                ),
                type_=new_training_alert_metric,
                existing_nullable=False,
            )


def downgrade() -> None:  # pragma: no cover - best-effort reversal
    bind = op.get_bind()
    op.drop_column("evaluation_jobs", "trigger_mode")
    evaluation_trigger_mode.drop(bind, checkfirst=True)
    # Enum value removal is intentionally skipped to avoid data loss on Postgres.

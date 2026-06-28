"""add model registry, alerts, dedupe fingerprint

Revision ID: 20260517_0001
Revises: 
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260517_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score_profit_mae", sa.Float(), nullable=True),
        sa.Column("score_roi_mae", sa.Float(), nullable=True),
        sa.Column("trained_on_samples", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_model_versions_model_name", "model_versions", ["model_name"])

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("samples", sa.Integer(), nullable=True),
        sa.Column("version_produced", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=64), nullable=True),
        sa.Column("consumed_checkpoint_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_training_runs_model_name", "training_runs", ["model_name"])

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_alert_events_code", "alert_events", ["code"])
    op.create_index("ix_alert_events_source", "alert_events", ["source"])
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"])

    with op.batch_alter_table("listings") as batch:
        batch.add_column(sa.Column("dedupe_fingerprint", sa.String(length=255), nullable=True))
    op.create_index("ix_listings_dedupe_fingerprint", "listings", ["dedupe_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_listings_dedupe_fingerprint", table_name="listings")
    with op.batch_alter_table("listings") as batch:
        batch.drop_column("dedupe_fingerprint")

    op.drop_index("ix_alert_events_created_at", table_name="alert_events")
    op.drop_index("ix_alert_events_source", table_name="alert_events")
    op.drop_index("ix_alert_events_code", table_name="alert_events")
    op.drop_table("alert_events")

    op.drop_index("ix_training_runs_model_name", table_name="training_runs")
    op.drop_table("training_runs")

    op.drop_index("ix_model_versions_model_name", table_name="model_versions")
    op.drop_table("model_versions")

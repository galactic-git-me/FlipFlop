"""Add demand intelligence tables for Phase 3 (F3.1)

Enables demand metrics dashboard, CSV export, trend analysis, and predictive alerts.
- demand_metrics_snapshots: Denormalized metrics for fast dashboard
- demand_alerts: Threshold-based alerts for demand signals
- demand_export_audits: Audit trail of CSV exports

Revision ID: 20260823_0007
Revises: 20260823_0006
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20260823_0007"
down_revision = "20260823_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Demand metrics snapshots (denormalized for dashboard)
    op.create_table(
        "demand_metrics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impression_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversion_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("view_to_conversion_rate", sa.Float(), nullable=True),
        sa.Column("sell_through_rate", sa.Float(), nullable=True),
        sa.Column("views_per_day", sa.Float(), nullable=True),
        sa.Column("conversions_per_day", sa.Float(), nullable=True),
        sa.Column("demand_trend", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("trend_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("volatility_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_demand_metrics_manual_build_id", "manual_build_id"),
        sa.Index("ix_demand_metrics_recorded_at", "recorded_at"),
    )

    # Demand alerts (threshold-based)
    op.create_table(
        "demand_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(30), nullable=False),  # high_demand, low_demand, risk_flag
        sa.Column("severity", sa.String(20), nullable=False),    # info, warning, critical
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("metric_name", sa.String(50), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_demand_alerts_manual_build_id", "manual_build_id"),
        sa.Index("ix_demand_alerts_alert_type", "alert_type"),
        sa.Index("ix_demand_alerts_created_at", "created_at"),
    )

    # Export audit trail
    op.create_table(
        "demand_export_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("export_type", sa.String(30), nullable=False),
        sa.Column("filter_params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("exported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_demand_export_audits_exported_at", "exported_at"),
    )


def downgrade() -> None:
    op.drop_table("demand_export_audits")
    op.drop_table("demand_alerts")
    op.drop_table("demand_metrics_snapshots")

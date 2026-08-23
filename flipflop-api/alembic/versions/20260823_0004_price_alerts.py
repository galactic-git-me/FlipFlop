"""Add price alerts table for Phase 2

Enables users to set price-drop alerts on specific builds.
- User can set target price threshold
- Alert sent when actual price drops below target
- History tracked for audit trail

Revision ID: 20260823_0004
Revises: 20260823_0003
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20260823_0004"
down_revision = "20260823_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Price alerts: user can set target price thresholds
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("target_price_gbp", sa.Integer(), nullable=False),  # Stored in pennies
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("triggered_at", sa.DateTime(), nullable=True),
        sa.Column("triggered_price_gbp", sa.Integer(), nullable=True),  # Pennies
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_price_alerts_manual_build_id", "manual_build_id"),
        sa.Index("ix_price_alerts_user_email", "user_email"),
        sa.Index("ix_price_alerts_is_active", "is_active"),
    )

    # Alert history: audit trail of triggered alerts
    op.create_table(
        "price_alert_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),  # triggered, acknowledged, dismissed, re_armed
        sa.Column("price_gbp", sa.Integer(), nullable=True),  # Pennies
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["alert_id"], ["price_alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_price_alert_events_alert_id", "alert_id"),
    )


def downgrade() -> None:
    op.drop_table("price_alert_events")
    op.drop_table("price_alerts")

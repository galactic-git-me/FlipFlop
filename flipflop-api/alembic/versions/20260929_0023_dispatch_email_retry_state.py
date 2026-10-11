"""Persist dispatch notification retry state.

Revision ID: 20260929_0023
Revises: 20260929_0022
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0023"
down_revision = "20260929_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipment_tracking_events",
        sa.Column("customer_notification_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "shipment_tracking_events",
        sa.Column("customer_notification_attempted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shipment_tracking_events", "customer_notification_attempted_at")
    op.drop_column("shipment_tracking_events", "customer_notification_attempts")

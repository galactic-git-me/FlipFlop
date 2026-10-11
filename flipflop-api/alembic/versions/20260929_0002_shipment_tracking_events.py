"""Add provider-neutral shipment tracking events.

Revision ID: 20260929_0002
Revises: 20260929_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0002"
down_revision = "20260929_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipment_tracking_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id"), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_event_id", sa.String(length=200), nullable=True, unique=True),
        sa.Column("status_code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("tracking_url", sa.String(length=1000), nullable=True),
        sa.Column("live_map_url", sa.String(length=1000), nullable=True),
        sa.Column("material", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("customer_notified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(order_id IS NOT NULL AND manual_build_id IS NULL) OR (order_id IS NULL AND manual_build_id IS NOT NULL)", name="ck_shipment_event_one_source"),
    )
    op.create_index("ix_shipment_tracking_events_order_id", "shipment_tracking_events", ["order_id"])
    op.create_index("ix_shipment_tracking_events_manual_build_id", "shipment_tracking_events", ["manual_build_id"])
    op.create_index("ix_shipment_tracking_events_provider_event_id", "shipment_tracking_events", ["provider_event_id"])
    op.create_index("ix_shipment_tracking_events_status_code", "shipment_tracking_events", ["status_code"])


def downgrade() -> None:
    op.drop_table("shipment_tracking_events")

"""Persist shipment booking attempt state to prevent duplicate charges.

Revision ID: 20260929_0004
Revises: 20260929_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0004"
down_revision = "20260929_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_builds",
        sa.Column("shipment_booking_state", sa.String(length=40), nullable=False, server_default="not_started"),
    )
    op.add_column("manual_builds", sa.Column("shipment_booking_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("shipment_booking_error_code", sa.String(length=80), nullable=True))

    # Preserve the already-booked fact for rows created before this guard.
    op.execute(
        "UPDATE manual_builds SET shipment_booking_state = 'booked' "
        "WHERE parcel2go_order_id IS NOT NULL OR shipment_booked_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("manual_builds", "shipment_booking_error_code")
    op.drop_column("manual_builds", "shipment_booking_attempted_at")
    op.drop_column("manual_builds", "shipment_booking_state")

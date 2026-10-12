"""Persist Parcel2Go shipment-level IDs for tracking callbacks.

Revision ID: 20260929_0017
Revises: 20260929_0016
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0017"
down_revision = "20260929_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_builds",
        sa.Column("parcel2go_order_line_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_manual_builds_parcel2go_order_line_id",
        "manual_builds",
        ["parcel2go_order_line_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_manual_builds_parcel2go_order_line_id", table_name="manual_builds")
    op.drop_column("manual_builds", "parcel2go_order_line_id")

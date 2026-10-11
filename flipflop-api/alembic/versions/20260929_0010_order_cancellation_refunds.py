"""Persist customer cancellations and full-refund reconciliation state.

Revision ID: 20260929_0010
Revises: 20260929_0009
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0010"
down_revision = "20260929_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        # SQLAlchemy's OrderStatus enum stores member names in this PostgreSQL enum.
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")
    op.add_column("orders", sa.Column("cancellation_requested_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("cancellation_status", sa.String(length=32), nullable=True))
    op.add_column("orders", sa.Column("refund_id", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "refund_id")
    op.drop_column("orders", "cancellation_status")
    op.drop_column("orders", "cancellation_requested_at")
    # PostgreSQL enum values are intentionally retained; removing one is unsafe
    # when any row or deployed process may still reference it.

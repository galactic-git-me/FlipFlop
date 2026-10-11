"""Keep private made-to-order checkout addresses outside Stripe metadata.

Revision ID: 20260929_0011
Revises: 20260929_0010
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0011"
down_revision = "20260929_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_checkout_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_intent_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_address", sa.JSON(), nullable=False),
        sa.Column("billing_address", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_order_checkout_snapshots_payment_intent_id", "order_checkout_snapshots", ["payment_intent_id"])
    op.create_index("ix_order_checkout_snapshots_customer_id", "order_checkout_snapshots", ["customer_id"])
    op.create_index("ix_order_checkout_snapshots_expires_at", "order_checkout_snapshots", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_order_checkout_snapshots_expires_at", table_name="order_checkout_snapshots")
    op.drop_index("ix_order_checkout_snapshots_customer_id", table_name="order_checkout_snapshots")
    op.drop_index("ix_order_checkout_snapshots_payment_intent_id", table_name="order_checkout_snapshots")
    op.drop_table("order_checkout_snapshots")

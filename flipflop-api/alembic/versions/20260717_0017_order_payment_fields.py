"""Order payment fields

Adds stripe_payment_intent_id (the real idempotency/lookup key for
payment confirmation, replacing the old approach of matching it out of
the free-text `notes` column) and makes promised_delivery_date nullable
(order creation doesn't compute a real delivery estimate yet, and both
payments.py and webhooks.py were passing None into a NOT NULL column).

Revision ID: 20260717_0017
Revises: 20260707_0016
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_0017"
down_revision = "20260707_0016"
depends_on = None


def upgrade():
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("stripe_payment_intent_id", sa.String(), nullable=True))
        batch.alter_column("promised_delivery_date", existing_type=sa.DateTime(), nullable=True)
    op.create_index(
        "ix_orders_stripe_payment_intent_id", "orders", ["stripe_payment_intent_id"]
    )


def downgrade():
    op.drop_index("ix_orders_stripe_payment_intent_id", table_name="orders")
    with op.batch_alter_table("orders") as batch:
        batch.alter_column("promised_delivery_date", existing_type=sa.DateTime(), nullable=False)
        batch.drop_column("stripe_payment_intent_id")

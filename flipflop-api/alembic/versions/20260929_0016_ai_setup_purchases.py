"""Persist admin-priced Getting Ready AI offers and purchases.

Revision ID: 20260929_0016
Revises: 20260929_0015
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0016"
down_revision = "20260929_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("ai_setup_offers", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column("app_settings", "ai_setup_offers", server_default=None)
    op.create_table(
        "ai_setup_purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_id", sa.String(length=80), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(length=100), nullable=False),
        sa.Column("amount_gbp", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("offer_snapshot", sa.JSON(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_id", "offer_id", name="uq_ai_setup_purchase_order_offer"),
        sa.UniqueConstraint("stripe_payment_intent_id", name="uq_ai_setup_purchase_payment_intent"),
    )
    op.create_index("ix_ai_setup_purchases_order_id", "ai_setup_purchases", ["order_id"])
    op.create_index("ix_ai_setup_purchases_customer_id", "ai_setup_purchases", ["customer_id"])
    op.create_index("ix_ai_setup_purchases_status", "ai_setup_purchases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_setup_purchases_status", table_name="ai_setup_purchases")
    op.drop_index("ix_ai_setup_purchases_customer_id", table_name="ai_setup_purchases")
    op.drop_index("ix_ai_setup_purchases_order_id", table_name="ai_setup_purchases")
    op.drop_table("ai_setup_purchases")
    op.drop_column("app_settings", "ai_setup_offers")
